from __future__ import annotations

import io
import json
import logging
import os
import tarfile
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import cast
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from uuid import UUID, uuid4

from sqlalchemy import Engine

from .execution_claims import ExecutionClaimRepository
from .execution_domain import ExecutionStatus
from .execution_results import (
    DispatchPackage,
    TrustedExecutionProjection,
    TrustedResultError,
    load_dispatch_package,
    load_expected_tests,
    parse_runner_result,
    persist_terminal_result,
    sandbox_request,
    trusted_compare,
)
from .execution_submission import finalize_submission

logger = logging.getLogger("skillforge.vercel-sandbox")
VERCEL_SANDBOX_ADAPTER = "VERCEL_SANDBOX"
MAX_RESPONSE_BYTES = 512 * 1024
DEFAULT_LEASE_SECONDS = 180


class VercelSandboxError(RuntimeError):
    pass


PYTHON_RUNNER = r'''from __future__ import annotations

import builtins
import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

MAX_CAPTURE = 65536
SAFE_MODULES = {
    "bisect", "collections", "dataclasses", "datetime", "decimal", "enum",
    "functools", "heapq", "inspect", "itertools", "math", "operator", "re",
    "statistics", "string", "typing"
}

CHILD = r"""
import builtins
import contextlib
import io
import json
import sys

MAX_CAPTURE = 65536
SAFE_MODULES = {
    "bisect", "collections", "dataclasses", "datetime", "decimal", "enum",
    "functools", "heapq", "inspect", "itertools", "math", "operator", "re",
    "statistics", "string", "typing"
}

class BoundedText(io.StringIO):
    def __init__(self, limit):
        super().__init__()
        self.limit = limit
        self.used = 0
        self.truncated = False
    def write(self, value):
        text = str(value)
        remaining = max(0, self.limit - self.used)
        if remaining:
            chunk = text[:remaining]
            super().write(chunk)
            self.used += len(chunk)
        if len(text) > remaining:
            self.truncated = True
        return len(text)

real_import = builtins.__import__
def controlled_import(name, globals=None, locals=None, fromlist=(), level=0):
    root = name.split('.', 1)[0]
    if root not in SAFE_MODULES:
        raise ImportError('module is unavailable in candidate execution')
    return real_import(name, globals, locals, fromlist, level)

safe_builtins = dict(vars(builtins))
for blocked in ('breakpoint', 'compile', 'eval', 'exec', 'input', 'open'):
    safe_builtins.pop(blocked, None)
safe_builtins['__import__'] = controlled_import
payload = json.load(sys.stdin)
stdout = BoundedText(MAX_CAPTURE)
stderr = BoundedText(MAX_CAPTURE)
result = {
    'ok': False,
    'actual': None,
    'error_category': None,
    'stdout': '',
    'stderr': '',
    'stdout_truncated': False,
    'stderr_truncated': False,
}
try:
    namespace = {'__builtins__': safe_builtins, '__name__': 'candidate_submission'}
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        code = compile(payload['source_code'], 'submission.py', 'exec')
        exec(code, namespace, namespace)
        candidate = namespace.get(payload['entrypoint'])
        if not callable(candidate):
            raise TypeError('required entrypoint is not callable')
        value = payload.get('input')
        mode = payload.get('invocation_mode', 'auto')
        if mode == 'keyword_arguments' or (mode == 'auto' and isinstance(value, dict)):
            actual = candidate(**value)
        elif mode == 'positional_arguments' or (mode == 'auto' and isinstance(value, list)):
            if not isinstance(value, list):
                raise TypeError('positional_arguments input must be a list')
            actual = candidate(*value)
        elif mode == 'no_arguments':
            actual = candidate()
        else:
            actual = candidate(value)
    json.dumps(actual)
    result['ok'] = True
    result['actual'] = actual
except BaseException as exc:
    result['error_category'] = type(exc).__name__
finally:
    result['stdout'] = stdout.getvalue()
    result['stderr'] = stderr.getvalue()
    result['stdout_truncated'] = stdout.truncated
    result['stderr_truncated'] = stderr.truncated
print(json.dumps(result, separators=(',', ':'), ensure_ascii=False))
"""


def run_child(payload, timeout_seconds):
    proc = subprocess.Popen(
        [sys.executable, '-I', '-S', '-c', CHILD],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        cwd='/home/vercel-sandbox',
        env={
            'HOME': '/home/vercel-sandbox',
            'LANG': 'C.UTF-8',
            'LC_ALL': 'C.UTF-8',
            'PATH': '/usr/local/bin:/usr/bin:/bin',
            'PYTHONHASHSEED': '0',
            'PYTHONIOENCODING': 'utf-8',
            'PYTHONUNBUFFERED': '1',
            'TMPDIR': '/tmp',
        },
        start_new_session=True,
    )
    try:
        stdout, stderr = proc.communicate(
            json.dumps(payload, separators=(',', ':'), ensure_ascii=False),
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired:
        try:
            os.killpg(proc.pid, 9)
        except ProcessLookupError:
            pass
        proc.communicate()
        return {
            'ok': False,
            'actual': None,
            'error_category': 'timeout',
            'stdout': '',
            'stderr': '',
        }, 124
    try:
        value = json.loads(stdout.strip())
    except json.JSONDecodeError:
        value = {
            'ok': False,
            'actual': None,
            'error_category': 'runner_protocol_error',
            'stdout': '',
            'stderr': stderr[:MAX_CAPTURE],
        }
    return value, proc.returncode or 0


def main():
    input_path = Path(sys.argv[1])
    output_path = Path(sys.argv[2])
    timeout_seconds = max(1, min(30, int(sys.argv[3])))
    request = json.loads(input_path.read_text(encoding='utf-8'))
    started = time.monotonic()
    deadline = started + timeout_seconds
    results = []
    public_stdout = []
    public_stderr = []
    status = 'COMPLETED'
    exit_code = 0
    for test in request['tests']:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            status = 'TIMEOUT'
            exit_code = 124
            break
        child, exit_code = run_child(
            {
                'source_code': request['source_code'],
                'entrypoint': request.get('entrypoint', 'solve'),
                'invocation_mode': request.get('invocation_mode', 'auto'),
                'input': test.get('input'),
            },
            max(1, min(timeout_seconds, int(remaining + 0.999))),
        )
        category = child.get('error_category')
        if category == 'timeout':
            status = 'TIMEOUT'
        results.append({
            'id': str(test['id']),
            'visibility': str(test.get('visibility', 'hidden')),
            'ok': bool(child.get('ok')),
            'actual': child.get('actual'),
            'error_category': str(category) if category else None,
        })
        if test.get('visibility') == 'public':
            public_stdout.append(str(child.get('stdout') or ''))
            public_stderr.append(str(child.get('stderr') or ''))
        if status == 'TIMEOUT':
            break
    result = {
        'schema_version': 1,
        'execution_id': str(request['execution_id']),
        'attempt': int(request['attempt']),
        'status': status,
        'runtime_ms': round((time.monotonic() - started) * 1000),
        'exit_code': exit_code,
        'tests': results,
        'stdout': ''.join(public_stdout)[:MAX_CAPTURE],
        'stderr': ''.join(public_stderr)[:MAX_CAPTURE],
    }
    output_path.write_text(
        'RIGOR_EXECUTION_RESULT:' + json.dumps(result, separators=(',', ':'), ensure_ascii=False),
        encoding='utf-8',
    )

if __name__ == '__main__':
    main()
'''


SQL_RUNNER = r'''from __future__ import annotations

import json
import os
import sys
import time
from datetime import date, datetime, time as dt_time
from decimal import Decimal
from pathlib import Path
from uuid import UUID

import psycopg
from psycopg import sql
from psycopg.errors import QueryCanceled

MAX_ROWS = 10000
MAX_RESULT_BYTES = 256 * 1024


def json_value(value):
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if value == float('inf'):
            return 'Infinity'
        if value == float('-inf'):
            return '-Infinity'
        if value != value:
            return 'NaN'
        return value
    if isinstance(value, Decimal):
        if value.is_nan():
            return 'NaN'
        if value.is_infinite():
            return 'Infinity' if value > 0 else '-Infinity'
        integral = value.to_integral_value()
        return int(integral) if value == integral else float(value)
    if isinstance(value, (date, datetime, dt_time)):
        return value.isoformat()
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, bytes):
        return value.hex()
    if isinstance(value, (list, tuple)):
        return [json_value(item) for item in value]
    if isinstance(value, dict):
        return {str(key): json_value(item) for key, item in value.items()}
    return str(value)


def conn(candidate=False):
    return {
        'host': '127.0.0.1',
        'port': 5432,
        'dbname': 'rigor_execution',
        'user': 'rigor_sql_candidate' if candidate else 'rigor_sql_owner',
        'password': os.environ['RIGOR_SQL_CANDIDATE_PASSWORD'] if candidate else os.environ['RIGOR_SQL_OWNER_PASSWORD'],
        'connect_timeout': 3,
    }


def reset_fixture(owner, request, test):
    value = test.get('input')
    test_schema = None
    test_seed = None
    setup = ''
    if isinstance(value, str):
        setup = value
    elif isinstance(value, dict):
        test_schema = value.get('schema_sql', value.get('ddl'))
        if 'seed_sql' in value or 'seed' in value:
            test_seed = value.get('seed_sql', value.get('seed'))
        setup = value.get('setup_sql') or ''
    owner.execute('DROP SCHEMA IF EXISTS public CASCADE')
    owner.execute('CREATE SCHEMA public')
    owner.execute('REVOKE ALL ON SCHEMA public FROM PUBLIC')
    owner.execute(str(test_schema or request['schema_sql']))
    seed = request.get('seed_sql', '') if test_seed is None else test_seed
    if seed:
        owner.execute(str(seed))
    if setup:
        owner.execute(str(setup))
    owner.execute('GRANT USAGE ON SCHEMA public TO rigor_sql_candidate')
    owner.execute('GRANT SELECT ON ALL TABLES IN SCHEMA public TO rigor_sql_candidate')
    owner.execute('GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO rigor_sql_candidate')


def candidate_query(source, timeout_ms):
    try:
        with psycopg.connect(**conn(True), autocommit=True) as candidate:
            candidate.execute("SELECT set_config('statement_timeout', %s, false)", (f'{timeout_ms}ms',))
            candidate.execute("SELECT set_config('lock_timeout', %s, false)", ('1000ms',))
            with candidate.cursor() as cursor:
                cursor.execute(source, prepare=True)
                if cursor.description is None:
                    actual = {'columns': [], 'rows': []}
                else:
                    columns = [column.name for column in cursor.description]
                    rows = cursor.fetchmany(MAX_ROWS + 1)
                    if len(rows) > MAX_ROWS:
                        return False, None, 'result_row_limit'
                    actual = {
                        'columns': columns,
                        'rows': [[json_value(cell) for cell in row] for row in rows],
                    }
                encoded = json.dumps(actual, separators=(',', ':'), ensure_ascii=False).encode()
                if len(encoded) > MAX_RESULT_BYTES:
                    return False, None, 'result_size_limit'
                return True, actual, None
    except psycopg.Error as exc:
        if isinstance(exc, QueryCanceled) or exc.sqlstate == '57014':
            return False, None, 'timeout'
        if exc.sqlstate == '42501':
            return False, None, 'sql_permission_denied'
        if exc.sqlstate == '42601':
            return False, None, 'sql_syntax_error'
        return False, None, 'sql_error'


def main():
    request = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
    output = Path(sys.argv[2])
    started = time.monotonic()
    status = 'COMPLETED'
    results = []
    with psycopg.connect(**conn(False), autocommit=True) as owner:
        for test in request['tests']:
            reset_fixture(owner, request, test)
            ok, actual, category = candidate_query(
                str(request['source_code']), int(request['statement_timeout_ms'])
            )
            if category == 'timeout':
                status = 'TIMEOUT'
            results.append({
                'id': str(test['id']),
                'visibility': str(test.get('visibility', 'hidden')),
                'ok': ok,
                'actual': actual,
                'error_category': category,
            })
            if status == 'TIMEOUT':
                break
    result = {
        'schema_version': 1,
        'execution_id': str(request['execution_id']),
        'attempt': int(request['attempt']),
        'status': status,
        'runtime_ms': round((time.monotonic() - started) * 1000),
        'exit_code': 124 if status == 'TIMEOUT' else 0,
        'tests': results,
        'stdout': '',
        'stderr': '',
    }
    output.write_text(
        'RIGOR_EXECUTION_RESULT:' + json.dumps(result, separators=(',', ':'), ensure_ascii=False),
        encoding='utf-8',
    )

if __name__ == '__main__':
    main()
'''


@dataclass(frozen=True)
class SandboxSession:
    session_id: str
    name: str


@dataclass(frozen=True)
class VercelSandboxClient:
    token: str
    project_id: str
    team_id: str | None = None
    api_origin: str = "https://api.vercel.com"

    @classmethod
    def discover(cls) -> VercelSandboxClient:
        token = os.getenv("VERCEL_OIDC_TOKEN") or os.getenv("VERCEL_TOKEN") or ""
        project_id = os.getenv("VERCEL_PROJECT_ID") or os.getenv("RIGOR_VERCEL_PROJECT_ID") or ""
        if not token:
            raise VercelSandboxError(
                "Vercel Sandbox authentication is unavailable; VERCEL_OIDC_TOKEN is missing."
            )
        if not project_id:
            raise VercelSandboxError(
                "Vercel Sandbox project scope is unavailable; VERCEL_PROJECT_ID is missing."
            )
        return cls(
            token=token,
            project_id=project_id,
            team_id=os.getenv("VERCEL_TEAM_ID") or None,
        )

    def _url(self, path: str) -> str:
        if self.team_id:
            separator = "&" if "?" in path else "?"
            return f"{self.api_origin}{path}{separator}teamId={self.team_id}"
        return f"{self.api_origin}{path}"

    def _request(
        self,
        path: str,
        *,
        method: str = "GET",
        body: bytes | None = None,
        content_type: str = "application/json",
        headers: dict[str, str] | None = None,
        timeout: float = 30.0,
    ) -> bytes:
        merged = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/json",
            "Content-Type": content_type,
            **(headers or {}),
        }
        request = Request(
            self._url(path),
            data=body,
            method=method,
            headers=merged,
        )
        try:
            with urlopen(request, timeout=timeout) as response:
                value = response.read(MAX_RESPONSE_BYTES + 1)
        except HTTPError as exc:
            detail = exc.read(4096).decode("utf-8", errors="replace")
            raise VercelSandboxError(
                f"Vercel Sandbox API returned HTTP {exc.code}: {detail[:500]}"
            ) from exc
        except (URLError, TimeoutError) as exc:
            raise VercelSandboxError("Vercel Sandbox API is unreachable.") from exc
        if len(value) > MAX_RESPONSE_BYTES:
            raise VercelSandboxError("Vercel Sandbox API response exceeded the transport limit.")
        return value

    def _json_request(
        self,
        path: str,
        *,
        method: str = "GET",
        payload: dict[str, object] | None = None,
        timeout: float = 30.0,
    ) -> dict[str, object]:
        raw = self._request(
            path,
            method=method,
            body=(
                json.dumps(payload, separators=(",", ":")).encode("utf-8")
                if payload is not None
                else None
            ),
            timeout=timeout,
        )
        try:
            decoded: object = json.loads(raw or b"{}")
        except json.JSONDecodeError as exc:
            raise VercelSandboxError("Vercel Sandbox API returned invalid JSON.") from exc
        if not isinstance(decoded, dict):
            raise VercelSandboxError("Vercel Sandbox API returned an invalid object.")
        return cast(dict[str, object], decoded)

    def create(
        self,
        *,
        execution_id: UUID,
        runtime: str,
        timeout_ms: int,
        allow_package_bootstrap: bool = False,
    ) -> SandboxSession:
        name = f"skillforge-{execution_id.hex[:18]}-{uuid4().hex[:6]}"
        network: dict[str, object]
        if allow_package_bootstrap:
            network = {
                "mode": "custom",
                "allowedDomains": [
                    "deb.debian.org",
                    "security.debian.org",
                    "archive.ubuntu.com",
                    "security.ubuntu.com",
                    "ports.ubuntu.com",
                ],
                "allowedCIDRs": [],
                "deniedCIDRs": [],
            }
        else:
            network = {"mode": "deny-all"}
        response = self._json_request(
            "/v2/sandboxes",
            method="POST",
            payload={
                "name": name,
                "projectId": self.project_id,
                "runtime": runtime,
                "timeout": str(timeout_ms),
                "persistent": False,
                "networkPolicy": network,
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

    def update_network_policy(self, session: SandboxSession, mode: str) -> None:
        self._json_request(
            f"/v2/sandboxes/sessions/{session.session_id}/network-policy",
            method="POST",
            payload={"mode": mode},
            timeout=15,
        )

    def upload_files(self, session: SandboxSession, files: dict[str, bytes]) -> None:
        buffer = io.BytesIO()
        with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
            for name, content in files.items():
                info = tarfile.TarInfo(name=name)
                info.size = len(content)
                info.mode = 0o600
                archive.addfile(info, io.BytesIO(content))
        self._request(
            f"/v2/sandboxes/sessions/{session.session_id}/fs/write",
            method="POST",
            body=buffer.getvalue(),
            content_type="application/gzip",
            headers={"x-cwd": "/home/vercel-sandbox"},
            timeout=30,
        )

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
        # With wait=true Vercel may return JSON or ND-JSON status frames. The
        # trusted result itself is read from result.log, so a successful HTTP
        # response is sufficient here.
        if not raw:
            return

    def read_file(self, session: SandboxSession, path: str) -> bytes:
        return self._request(
            f"/v2/sandboxes/sessions/{session.session_id}/fs/read",
            method="POST",
            body=json.dumps(
                {"cwd": "/home/vercel-sandbox", "path": path}, separators=(",", ":")
            ).encode("utf-8"),
            timeout=15,
        )

    def stop(self, session: SandboxSession) -> None:
        try:
            self._json_request(
                f"/v2/sandboxes/sessions/{session.session_id}/stop",
                method="POST",
                payload={},
                timeout=15,
            )
        except VercelSandboxError:
            logger.warning(
                "vercel_sandbox.stop_failed",
                extra={"session_id": session.session_id},
                exc_info=True,
            )

    def run_python(self, package: DispatchPackage, payload: dict[str, object]) -> str:
        timeout_seconds = _positive_limit(package.limits, "execution_timeout_seconds", 10)
        request_payload = {
            **payload,
            "invocation_mode": str(package.input_payload.get("invocation_mode") or "auto"),
        }
        session = self.create(
            execution_id=package.execution_id,
            runtime="python3.13",
            timeout_ms=max(45_000, (timeout_seconds + 20) * 1000),
        )
        try:
            self.upload_files(
                session,
                {
                    "runner.py": PYTHON_RUNNER.encode("utf-8"),
                    "input.json": json.dumps(
                        request_payload, separators=(",", ":"), ensure_ascii=False
                    ).encode("utf-8"),
                },
            )
            self.execute(
                session,
                command="python",
                args=["runner.py", "input.json", "result.log", str(timeout_seconds)],
                timeout_ms=(timeout_seconds + 8) * 1000,
            )
            return self.read_file(session, "result.log").decode("utf-8", errors="replace")
        finally:
            self.stop(session)

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
            bootstrap = f"""
set -eu
export DEBIAN_FRONTEND=noninteractive
if ! command -v postgres >/dev/null 2>&1 || ! /usr/bin/python3 -c 'import psycopg' >/dev/null 2>&1; then
  apt-get update -qq
  apt-get install -y -qq postgresql python3-psycopg
fi
service postgresql start >/dev/null 2>&1 || true
sudo -u postgres psql -v ON_ERROR_STOP=1 postgres <<'SQL'
DROP DATABASE IF EXISTS rigor_execution;
DROP ROLE IF EXISTS rigor_sql_candidate;
DROP ROLE IF EXISTS rigor_sql_owner;
CREATE ROLE rigor_sql_owner LOGIN SUPERUSER PASSWORD '{owner_password}';
CREATE ROLE rigor_sql_candidate LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS PASSWORD '{candidate_password}';
CREATE DATABASE rigor_execution OWNER rigor_sql_owner;
SQL
"""
            self.execute(
                session,
                command="sh",
                args=["-lc", bootstrap],
                timeout_ms=120_000,
                sudo=True,
            )
            # Candidate SQL runs only after all package installation is complete
            # and egress has been fully closed.
            self.update_network_policy(session, "deny-all")
            self.upload_files(
                session,
                {
                    "runner.py": SQL_RUNNER.encode("utf-8"),
                    "input.json": json.dumps(
                        payload, separators=(",", ":"), ensure_ascii=False
                    ).encode("utf-8"),
                },
            )
            command_timeout = min(45_000, max(10_000, statement_ms * 2 + 5000))
            self.execute(
                session,
                command="/usr/bin/python3",
                args=["runner.py", "input.json", "result.log"],
                timeout_ms=command_timeout,
                env={
                    "RIGOR_SQL_OWNER_PASSWORD": owner_password,
                    "RIGOR_SQL_CANDIDATE_PASSWORD": candidate_password,
                },
            )
            return self.read_file(session, "result.log").decode("utf-8", errors="replace")
        finally:
            self.stop(session)


def _positive_limit(limits: dict[str, object], key: str, default: int) -> int:
    value = limits.get(key)
    if isinstance(value, int) and not isinstance(value, bool) and value > 0:
        return value
    if isinstance(value, str):
        try:
            parsed = int(value)
        except ValueError:
            return default
        return parsed if parsed > 0 else default
    return default


def vercel_sandbox_enabled() -> bool:
    return os.getenv("RIGOR_EXECUTION_ADAPTER", "").strip().upper() == VERCEL_SANDBOX_ADAPTER


def _worker_id() -> str:
    deployment = os.getenv("VERCEL_DEPLOYMENT_ID") or os.getenv("VERCEL_URL") or "vercel"
    return f"vercel-sandbox:{deployment}"[:255]


def _infrastructure_projection(
    *,
    category: str,
    message: str,
) -> TrustedExecutionProjection:
    return TrustedExecutionProjection(
        execution_status=ExecutionStatus.failed,
        runtime_ms=0,
        exit_code=1,
        error_category=category,
        public_results=[],
        hidden_total=0,
        hidden_passed=0,
        stdout="",
        stderr="",
        candidate_message=message,
    )


def _persist_projection(
    engine: Engine,
    package: DispatchPackage,
    worker_id: str,
    projection: TrustedExecutionProjection,
) -> None:
    with engine.begin() as connection:
        if not ExecutionClaimRepository(connection).lock_owned_attempt(
            package.execution_id,
            worker_id=worker_id,
            attempt_count=package.attempt_count,
        ):
            return
        terminal = persist_terminal_result(
            connection,
            execution_id=package.execution_id,
            projection=projection,
        )
        if terminal == projection.execution_status:
            finalize_submission(connection, package=package, projection=projection)


def dispatch_vercel_execution(engine: Engine, execution_id: UUID) -> None:
    """Synchronously orchestrate one durable execution in Vercel Sandbox.

    Candidate source never runs in the FastAPI process. FastAPI only claims the
    durable request, sends the sanitized input to an isolated microVM, performs
    trusted comparison outside the sandbox, and persists the public projection.
    """

    if not vercel_sandbox_enabled():
        return
    worker_id = _worker_id()
    lease_seconds = max(
        DEFAULT_LEASE_SECONDS,
        int(os.getenv("RIGOR_VERCEL_SANDBOX_LEASE_SECONDS", str(DEFAULT_LEASE_SECONDS))),
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

    session_label = f"vercel-{package.execution_id}"
    try:
        payload = sandbox_request(package)
        client = VercelSandboxClient.discover()
        if package.language == "python":
            logs = client.run_python(package, payload)
        elif package.language == "sql":
            logs = client.run_sql(package, payload)
        else:
            raise VercelSandboxError("Execution language is unsupported by Vercel Sandbox.")

        with engine.begin() as connection:
            marked = ExecutionClaimRepository(connection).mark_running(
                package.execution_id,
                worker_id=worker_id,
                kubernetes_namespace="vercel-sandbox",
                kubernetes_job_name=session_label,
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
                message="The isolated execution service could not complete this run. Please retry.",
            ),
        )
