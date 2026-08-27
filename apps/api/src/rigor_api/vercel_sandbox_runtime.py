from __future__ import annotations

import json
import logging
import os
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import Engine

from .execution_claims import ExecutionClaimRepository
from .execution_results import (
    DispatchPackage,
    TrustedResultError,
    load_dispatch_package,
    load_expected_tests,
    parse_runner_result,
    sandbox_request,
    trusted_compare,
)
from .vercel_sandbox_execution import (
    DEFAULT_LEASE_SECONDS,
    SQL_RUNNER,
    SandboxSession,
    VercelSandboxClient,
    VercelSandboxError,
    _infrastructure_projection,
    _persist_projection,
    _positive_limit,
    _worker_id,
    vercel_sandbox_enabled,
)

logger = logging.getLogger("skillforge.vercel-sandbox-runtime")

# Vercel's current Sandbox examples use an Amazon-Linux-style image and dnf.
# Package egress is allowed only while trusted bootstrap code is running. Candidate
# source is not uploaded until after the policy is replaced with deny-all.
PACKAGE_BOOTSTRAP_DOMAINS = [
    "cdn.amazonlinux.com",
    "*.amazonaws.com",
    "pypi.org",
    "files.pythonhosted.org",
]


class HardenedVercelSandboxClient(VercelSandboxClient):
    """Vercel Sandbox client with checked commands and portable SQL bootstrap."""

    def create(
        self,
        *,
        execution_id: UUID,
        runtime: str,
        timeout_ms: int,
        allow_package_bootstrap: bool = False,
    ) -> SandboxSession:
        if not allow_package_bootstrap:
            return super().create(
                execution_id=execution_id,
                runtime=runtime,
                timeout_ms=timeout_ms,
                allow_package_bootstrap=False,
            )

        name = f"skillforge-{execution_id.hex[:18]}-{uuid4().hex[:6]}"
        response = self._json_request(
            "/v2/sandboxes",
            method="POST",
            payload={
                "name": name,
                "projectId": self.project_id,
                "runtime": runtime,
                "timeout": str(timeout_ms),
                "persistent": False,
                "networkPolicy": {
                    "mode": "custom",
                    "allowedDomains": PACKAGE_BOOTSTRAP_DOMAINS,
                    "allowedCIDRs": [],
                    "deniedCIDRs": [],
                },
            },
            timeout=30,
        )
        session_value = response.get("session")
        if not isinstance(session_value, dict):
            raise VercelSandboxError("Vercel Sandbox creation returned no session.")
        session_id = session_value.get("id")
        if not isinstance(session_id, str) or not session_id:
            raise VercelSandboxError("Vercel Sandbox creation returned no session id.")
        return SandboxSession(session_id=session_id, name=name)

    @staticmethod
    def _command_exit_code(raw: bytes) -> int:
        """Extract the final command exit code from JSON or ND-JSON wait output."""
        text = raw.decode("utf-8", errors="replace").strip()
        if not text:
            raise VercelSandboxError("Vercel Sandbox command returned no completion status.")

        frames: list[object] = []
        for line in text.splitlines():
            try:
                frames.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        if not frames:
            try:
                frames.append(json.loads(text))
            except json.JSONDecodeError as exc:
                raise VercelSandboxError(
                    "Vercel Sandbox command returned invalid completion data."
                ) from exc

        final_code: int | None = None
        for frame in frames:
            if not isinstance(frame, dict):
                continue
            command = frame.get("command")
            if not isinstance(command, dict):
                continue
            value = command.get("exitCode")
            if isinstance(value, int) and not isinstance(value, bool):
                final_code = value
            elif isinstance(value, str):
                try:
                    final_code = int(value)
                except ValueError:
                    continue
        if final_code is None:
            raise VercelSandboxError(
                "Vercel Sandbox command did not expose a terminal exit code."
            )
        return final_code

    def execute(
        self,
        session: SandboxSession,
        *,
        command: str,
        args: list[str],
        timeout_ms: int,
        env: dict[str, str] | None = None,
        sudo: bool = False,
    ) -> None:
        raw = self._request(
            f"/v2/sandboxes/sessions/{session.session_id}/cmd",
            method="POST",
            body=json.dumps(
                {
                    "command": command,
                    "args": args,
                    "cwd": "/home/vercel-sandbox",
                    "env": env or {},
                    "sudo": sudo,
                    "wait": True,
                    "logs": False,
                    "timeout": timeout_ms,
                },
                separators=(",", ":"),
            ).encode("utf-8"),
            timeout=max(30.0, timeout_ms / 1000 + 15),
        )
        exit_code = self._command_exit_code(raw)
        if exit_code != 0:
            raise VercelSandboxError(
                f"Vercel Sandbox command failed with exit code {exit_code}."
            )

    def run_sql(self, package: DispatchPackage, payload: dict[str, object]) -> str:
        statement_ms = payload.get("statement_timeout_ms")
        if not isinstance(statement_ms, int) or isinstance(statement_ms, bool):
            raise VercelSandboxError("SQL statement timeout is unavailable.")

        owner_password = uuid4().hex + uuid4().hex
        candidate_password = uuid4().hex + uuid4().hex
        session = self.create(
            execution_id=package.execution_id,
            runtime="python3.13",
            timeout_ms=180_000,
            allow_package_bootstrap=True,
        )
        try:
            # This command is trusted platform bootstrap only. Candidate SQL has
            # not been uploaded yet. We deliberately avoid systemd/service and
            # initialize a private PostgreSQL data directory inside the microVM.
            bootstrap = f"""
set -euo pipefail

dnf install -y postgresql15 postgresql15-server
python -m pip install --disable-pip-version-check --no-cache-dir 'psycopg[binary]==3.3.4'

id -u skillforge_pg >/dev/null 2>&1 || useradd --system --create-home --home-dir /tmp/skillforge-pg skillforge_pg
rm -rf /tmp/skillforge-pg/data /tmp/skillforge-pg/socket
install -d -m 0700 -o skillforge_pg -g skillforge_pg /tmp/skillforge-pg/data
install -d -m 0700 -o skillforge_pg -g skillforge_pg /tmp/skillforge-pg/socket

INITDB="$(command -v initdb)"
PG_CTL="$(command -v pg_ctl)"
PSQL="$(command -v psql)"

runuser -u skillforge_pg -- "$INITDB" -D /tmp/skillforge-pg/data -A trust --no-locale --encoding=UTF8 >/dev/null
cat >> /tmp/skillforge-pg/data/postgresql.conf <<'PGCONF'
listen_addresses = '127.0.0.1'
port = 5432
unix_socket_directories = '/tmp/skillforge-pg/socket'
max_connections = 20
shared_buffers = '32MB'
fsync = off
synchronous_commit = off
full_page_writes = off
PGCONF
runuser -u skillforge_pg -- "$PG_CTL" -D /tmp/skillforge-pg/data -w start >/dev/null

runuser -u skillforge_pg -- "$PSQL" -h 127.0.0.1 -p 5432 -v ON_ERROR_STOP=1 postgres <<'SQL'
DROP DATABASE IF EXISTS rigor_execution;
DROP ROLE IF EXISTS rigor_sql_candidate;
DROP ROLE IF EXISTS rigor_sql_owner;
CREATE ROLE rigor_sql_owner LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS PASSWORD '{owner_password}';
CREATE ROLE rigor_sql_candidate LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS PASSWORD '{candidate_password}';
CREATE DATABASE rigor_execution OWNER rigor_sql_owner;
REVOKE ALL ON DATABASE rigor_execution FROM PUBLIC;
GRANT CONNECT ON DATABASE rigor_execution TO rigor_sql_owner, rigor_sql_candidate;
SQL
"""
            self.execute(
                session,
                command="bash",
                args=["-lc", bootstrap],
                timeout_ms=120_000,
                sudo=True,
            )

            # From this point onward the sandbox has zero egress. Only after the
            # network closes do we upload candidate SQL and the trusted runner.
            self.update_network_policy(session, "deny-all")
            self.upload_files(
                session,
                {
                    "runner.py": SQL_RUNNER.encode("utf-8"),
                    "input.json": json.dumps(
                        payload,
                        separators=(",", ":"),
                        ensure_ascii=False,
                    ).encode("utf-8"),
                },
            )
            command_timeout = min(45_000, max(10_000, statement_ms * 2 + 5000))
            self.execute(
                session,
                command="python",
                args=["runner.py", "input.json", "result.log"],
                timeout_ms=command_timeout,
                env={
                    "RIGOR_SQL_OWNER_PASSWORD": owner_password,
                    "RIGOR_SQL_CANDIDATE_PASSWORD": candidate_password,
                },
            )
            return self.read_file(session, "result.log").decode(
                "utf-8", errors="replace"
            )
        finally:
            self.stop(session)


def dispatch_vercel_execution(engine: Engine, execution_id: UUID) -> None:
    """Dispatch one durable execution using the hardened Vercel Sandbox path."""
    if not vercel_sandbox_enabled():
        return

    worker_id = _worker_id()
    lease_seconds = max(
        DEFAULT_LEASE_SECONDS,
        int(
            os.getenv(
                "RIGOR_VERCEL_SANDBOX_LEASE_SECONDS",
                str(DEFAULT_LEASE_SECONDS),
            )
        ),
    )
    with engine.begin() as connection:
        claim = ExecutionClaimRepository(connection).claim_for_dispatch(
            execution_id,
            worker_id=worker_id,
            lease_expires_at=datetime.now(UTC) + timedelta(seconds=lease_seconds),
        )
        if claim is None:
            return
        package = load_dispatch_package(connection, execution_id)

    try:
        payload = sandbox_request(package)
        base = VercelSandboxClient.discover()
        client = HardenedVercelSandboxClient(
            token=base.token,
            project_id=base.project_id,
            team_id=base.team_id,
            api_origin=base.api_origin,
        )
        if package.language == "python":
            logs = client.run_python(package, payload)
        elif package.language == "sql":
            logs = client.run_sql(package, payload)
        else:
            raise VercelSandboxError(
                "Execution language is unsupported by Vercel Sandbox."
            )

        with engine.begin() as connection:
            marked = ExecutionClaimRepository(connection).mark_running(
                package.execution_id,
                worker_id=worker_id,
                kubernetes_namespace="vercel-sandbox",
                kubernetes_job_name=f"vercel-{package.execution_id}",
            )
        if not marked:
            return

        sandbox_result = parse_runner_result(
            logs,
            execution_id=package.execution_id,
            expected_attempt=package.attempt_count,
        )
        with engine.begin() as connection:
            expected = load_expected_tests(
                connection,
                question_version_id=package.question_version_id,
            )
        projection = trusted_compare(sandbox_result, expected)
        _persist_projection(engine, package, worker_id, projection)
    except (VercelSandboxError, TrustedResultError, ValueError) as exc:
        logger.exception(
            "vercel_sandbox.execution_failed",
            extra={
                "execution_id": str(execution_id),
                "attempt": package.attempt_count,
                "error": exc.__class__.__name__,
            },
        )
        _persist_projection(
            engine,
            package,
            worker_id,
            _infrastructure_projection(
                category="vercel_sandbox_infrastructure_error",
                message=(
                    "The isolated execution service could not complete this run. "
                    "Please retry."
                ),
            ),
        )
