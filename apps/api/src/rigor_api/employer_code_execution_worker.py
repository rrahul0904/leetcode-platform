"""Dedicated AWS SQS -> EKS/gVisor executor for employer coding assessments.

Invoked only with RIGOR_EXECUTOR_DATABASE_URL and a *dedicated* employer SQS URL.
Never share a learner queue: learner controller cannot interpret employer events.
Never import or execute submitted code in the controller or FastAPI process.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import socket
import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy import Engine, create_engine, text

from .employer_code_contract import (
    PrivateCodeBundle,
    canonical_bundle_digest,
    trusted_runner_contract,
)
from .execution_kubernetes import (
    KubernetesApiConfig,
    KubernetesSandboxExecutor,
    SandboxExecutor,
    SandboxHandle,
)
from .execution_results import (
    TrustedResultError,
    _test_passed,
    parse_runner_result,
    trusted_compare,
)
from .execution_sqs import SqsJsonClient, SqsReceivedMessage
from .sandbox_jobs import sandbox_job_name

logger = logging.getLogger("rigor.employer-code-worker")
TERMINAL = {"completed", "failed", "timeout"}
LEASE_SECONDS = 120
MAX_ATTEMPTS = 3


@dataclass(frozen=True)
class EmployerCodeWork:
    id: UUID
    language: str
    mode: str
    source: str
    source_sha256: str
    assessment_version_id: UUID
    organization_id: UUID
    question_number: int
    attempt_count: int


def parse_employer_event(body: str) -> UUID:
    try:
        value: object = json.loads(body)
    except json.JSONDecodeError as exc:
        raise ValueError("Employer queue event is malformed") from exc
    if not isinstance(value, dict):
        raise ValueError("Employer queue event must be an object")
    if set(value) != {"schema_version", "event_type", "execution_id"}:
        raise ValueError("Employer queue event fields are invalid")
    if value["schema_version"] != 1 or value["event_type"] != "employer_code.requested":
        raise ValueError("Unsupported employer queue event type")
    return UUID(str(value["execution_id"]))


class EmployerCodeWorker:
    def __init__(
        self,
        *,
        engine: Engine,
        queue: SqsJsonClient,
        sandbox: SandboxExecutor,
        worker_id: str,
    ) -> None:
        self.engine = engine
        self.queue = queue
        self.sandbox = sandbox
        self.worker_id = worker_id

    def publish_outbox_once(self) -> int:
        """Atomic delivery handoff, tolerating duplicate SQS deliveries."""
        published = 0
        with self.engine.begin() as connection:
            records = connection.execute(
                text(
                    """SELECT id, execution_id, attempt_count
                       FROM employer_code_execution_outbox
                       WHERE state='pending' AND next_attempt_at<=CURRENT_TIMESTAMP
                       ORDER BY created_at FOR UPDATE SKIP LOCKED LIMIT 25"""
                )
            ).mappings().all()
            for record in records:
                event = json.dumps({
                    "schema_version": 1,
                    "event_type": "employer_code.requested",
                    "execution_id": str(record["execution_id"]),
                }, separators=(",", ":"))
                try:
                    self.queue.send_message(event)
                except Exception:
                    logger.exception(
                        "employer_code.queue_publish_retry",
                        extra={"execution_id": str(record["execution_id"])},
                    )
                    connection.execute(
                        text(
                            """UPDATE employer_code_execution_outbox
                               SET attempt_count=attempt_count+1,
                                   next_attempt_at=CURRENT_TIMESTAMP
                                       + make_interval(secs=>LEAST(300,
                                         5 * POWER(2, LEAST(attempt_count, 6)))::int)
                               WHERE id=:id"""
                        ),
                        {"id": record["id"]},
                    )
                else:
                    connection.execute(
                        text(
                            """UPDATE employer_code_execution_outbox
                               SET state='published', published_at=CURRENT_TIMESTAMP
                               WHERE id=:id"""
                        ),
                        {"id": record["id"]},
                    )
                    published += 1
        return published

    def _claim(self, execution_id: UUID) -> tuple[EmployerCodeWork | None, bool]:
        """Return (work, acknowledged). Only one lease owner may commit a result."""
        with self.engine.begin() as conn:
            row = conn.execute(
                text(
                    """SELECT id, language, execution_mode, source_code, source_sha256,
                              organization_id, assessment_version_id, question_number,
                              status, attempt_count, lease_expires_at
                       FROM employer_code_executions
                       WHERE id=:execution FOR UPDATE"""
                ),
                {"execution": execution_id},
            ).mappings().one_or_none()
            if row is None:
                return None, True
            if row["status"] in TERMINAL:
                return None, True
            if row["status"] in {"dispatching", "running"} and (
                row["lease_expires_at"] is not None
                and row["lease_expires_at"] > datetime.now(UTC)
            ):
                return None, False
            if int(row["attempt_count"]) >= MAX_ATTEMPTS:
                conn.execute(
                    text(
                        """UPDATE employer_code_executions
                           SET status='failed', error_category='execution_attempt_limit',
                               lease_owner=NULL, lease_expires_at=NULL,
                               updated_at=CURRENT_TIMESTAMP
                           WHERE id=:execution"""
                    ),
                    {"execution": execution_id},
                )
                return None, True
            attempt = int(row["attempt_count"]) + 1
            conn.execute(
                text(
                    """UPDATE employer_code_executions
                       SET status='dispatching', attempt_count=:attempt,
                           lease_owner=:worker, lease_expires_at=:expires,
                           updated_at=CURRENT_TIMESTAMP
                       WHERE id=:execution"""
                ),
                {
                    "execution": execution_id, "attempt": attempt,
                    "worker": self.worker_id,
                    "expires": datetime.now(UTC) + timedelta(seconds=LEASE_SECONDS),
                },
            )
            return EmployerCodeWork(
                id=execution_id, language=str(row["language"]),
                mode=str(row["execution_mode"]), source=str(row["source_code"]),
                source_sha256=str(row["source_sha256"]),
                assessment_version_id=UUID(str(row["assessment_version_id"])),
                organization_id=UUID(str(row["organization_id"])),
                question_number=int(row["question_number"]),
                attempt_count=attempt,
            ), False

    def _bundle(self, work: EmployerCodeWork) -> PrivateCodeBundle:
        with self.engine.begin() as conn:
            row = conn.execute(
                text(
                    """SELECT v.content_sha256, v.status, p.private_rubric, p.source_sha256
                       FROM employer_assessment_versions v
                       JOIN employer_assessment_private_keys p
                         ON p.assessment_version_id=v.id
                        AND p.organization_id=v.organization_id
                       WHERE v.id=:version AND v.organization_id=:org"""
                ),
                {"version": work.assessment_version_id, "org": work.organization_id},
            ).mappings().one_or_none()
        if row is None or row["status"] != "published":
            raise TrustedResultError("Unpublished or revoked assessment is not executable")
        if row["source_sha256"] != row["content_sha256"]:
            raise TrustedResultError("Private rubric version mismatch")
        entry = row["private_rubric"].get("code_test_bundles", {}).get(
            str(work.question_number)
        )
        if not isinstance(entry, dict) or entry.get("source_sha256") != row["content_sha256"]:
            raise TrustedResultError("Private test fixture is unavailable or stale")
        try:
            payload = PrivateCodeBundle.model_validate(entry.get("bundle"))
        except ValidationError as exc:
            raise TrustedResultError("Private fixture schema invalid") from exc
        if payload.language != work.language:
            raise TrustedResultError("Assessment execution runtime changed")
        if canonical_bundle_digest(payload) != entry.get("bundle_sha256"):
            raise TrustedResultError("Private grading bundle integrity mismatch")
        if hashlib.sha256(work.source.encode("utf-8")).hexdigest() != work.source_sha256:
            raise TrustedResultError("Candidate code snapshot integrity mismatch")
        return payload

    def _renew(self, work: EmployerCodeWork) -> bool:
        with self.engine.begin() as conn:
            row = conn.execute(
                text(
                    """UPDATE employer_code_executions
                       SET lease_expires_at=:expires, updated_at=CURRENT_TIMESTAMP
                       WHERE id=:id AND lease_owner=:worker AND attempt_count=:attempt
                         AND status IN ('dispatching','running')
                         AND lease_expires_at>CURRENT_TIMESTAMP
                       RETURNING id"""
                ),
                {
                    "id": work.id, "worker": self.worker_id,
                    "attempt": work.attempt_count,
                    "expires": datetime.now(UTC) + timedelta(seconds=LEASE_SECONDS),
                },
            ).scalar_one_or_none()
        return row is not None

    def _complete(
        self,
        work: EmployerCodeWork,
        *,
        status: str,
        runtime_ms: int = 0,
        public_results: list[dict[str, object]] | None = None,
        hidden_total: int = 0,
        hidden_passed: int = 0,
        awarded_marks: int | None = None,
        error: str | None = None,
    ) -> bool:
        with self.engine.begin() as conn:
            row = conn.execute(
                text(
                    """UPDATE employer_code_executions
                       SET status=:status, runtime_ms=:duration,
                           public_results=CAST(:public AS jsonb),
                           hidden_total=:total, hidden_passed=:passed,
                           awarded_marks=:awarded, error_category=:error,
                           lease_owner=NULL, lease_expires_at=NULL,
                           updated_at=CURRENT_TIMESTAMP
                       WHERE id=:id AND lease_owner=:worker AND attempt_count=:attempt
                         AND status IN ('dispatching','running')
                         AND lease_expires_at>CURRENT_TIMESTAMP
                       RETURNING id"""
                ),
                {
                    "id": work.id, "worker": self.worker_id,
                    "attempt": work.attempt_count,
                    "status": status, "duration": runtime_ms,
                    "public": json.dumps(public_results or [], separators=(",", ":")),
                    "total": hidden_total, "passed": hidden_passed,
                    "awarded": awarded_marks, "error": error,
                },
            ).scalar_one_or_none()
        return row is not None

    def _requeue(self, work: EmployerCodeWork, error: str) -> bool:
        if work.attempt_count >= MAX_ATTEMPTS:
            return self._complete(work, status="failed", error="execution_attempt_limit")
        with self.engine.begin() as conn:
            conn.execute(
                text(
                    """UPDATE employer_code_executions
                       SET status='queued', lease_owner=NULL,
                           lease_expires_at=NULL, error_category=:error,
                           updated_at=CURRENT_TIMESTAMP
                       WHERE id=:id AND lease_owner=:worker AND attempt_count=:attempt"""
                ),
                {
                    "id": work.id, "worker": self.worker_id,
                    "attempt": work.attempt_count, "error": error,
                },
            )
        return False

    def process_message(self, message: SqsReceivedMessage) -> bool:
        try:
            execution_id = parse_employer_event(message.body)
        except (ValueError, TypeError):
            logger.error("employer_code.invalid_queue_event")
            self.queue.delete_message(message.receipt_handle)
            return True
        work, acknowledged = self._claim(execution_id)
        if work is None:
            if acknowledged:
                self.queue.delete_message(message.receipt_handle)
            return acknowledged

        handle: SandboxHandle | None = None
        cleanup_permitted = True
        try:
            # Reclaimed leases must not reuse a stale runner Pod with the same
            # execution UUID; its old attempt number could otherwise be graded.
            if work.attempt_count > 1:
                job = sandbox_job_name(work.id)
                namespace = os.getenv("RIGOR_EXECUTION_NAMESPACE", "rigor-execution")
                self.sandbox.cleanup(SandboxHandle(
                    execution_id=work.id, namespace=namespace,
                    job_name=job, input_secret_name=f"input-{job}",
                ))
            bundle = self._bundle(work)
            if work.mode == "RUN":
                bundle = bundle.model_copy(update={
                    "cases": [c for c in bundle.cases if c.visibility == "sample"],
                })
            request, expected = trusted_runner_contract(
                bundle, execution_id=work.id,
                attempt=work.attempt_count, source_code=work.source,
            )
            # This is the same resource-limited Kubernetes/gVisor executor as
            # learner practice. The worker is the only caller with K8s access.
            if work.language == "python":
                handle = self.sandbox.create_python_execution(
                    execution_id=work.id,
                    request_payload=request,
                    profile_name="python-small",
                )
            else:
                handle = self.sandbox.create_sql_execution(
                    execution_id=work.id,
                    request_payload=request,
                    profile_name="sql-small",
                )
            with self.engine.begin() as conn:
                conn.execute(
                    text(
                        """UPDATE employer_code_executions
                           SET status='running', job_namespace=:namespace,
                               job_name=:job, updated_at=CURRENT_TIMESTAMP
                           WHERE id=:id AND lease_owner=:worker
                             AND attempt_count=:attempt AND status='dispatching'"""
                    ),
                    {
                        "id": work.id, "worker": self.worker_id,
                        "attempt": work.attempt_count,
                        "namespace": handle.namespace, "job": handle.job_name,
                    },
                )
            deadline = time.monotonic() + 90
            next_renew = time.monotonic() + 25
            while time.monotonic() < deadline:
                observation = self.sandbox.observe(handle)
                if observation.state in {"SUCCEEDED", "FAILED"}:
                    if observation.logs is None:
                        raise TrustedResultError("Isolated runner returned no result")
                    runner = parse_runner_result(
                        observation.logs, execution_id=work.id,
                        expected_attempt=work.attempt_count,
                    )
                    projection = trusted_compare(runner, expected)
                    score = None
                    if work.mode == "SUBMIT" and runner.status == "COMPLETED":
                        points = {c.case_id: c.points for c in bundle.cases}
                        score = sum(
                            points[str(test["id"])]
                            for test in runner.tests
                            if _test_passed(test, expected[str(test["id"])])
                        )
                    result_status = {
                        "COMPLETED": "completed", "FAILED": "failed",
                        "TIMEOUT": "timeout",
                    }[runner.status]
                    done = self._complete(
                        work, status=result_status,
                        runtime_ms=projection.runtime_ms,
                        public_results=projection.public_results,
                        hidden_total=projection.hidden_total,
                        hidden_passed=projection.hidden_passed,
                        awarded_marks=score,
                        error=projection.error_category,
                    )
                    if done:
                        self.queue.delete_message(message.receipt_handle)
                    return done
                if observation.state == "MISSING":
                    raise TrustedResultError("Isolated Kubernetes execution disappeared")
                if time.monotonic() >= next_renew:
                    if not self._renew(work):
                        # Another worker owns this lease. Never delete its Pod.
                        cleanup_permitted = False
                        return False
                    self.queue.change_message_visibility(message.receipt_handle, 90)
                    next_renew = time.monotonic() + 25
                time.sleep(0.5)
            done = self._complete(work, status="timeout", error="execution_timeout")
            if done:
                self.queue.delete_message(message.receipt_handle)
            return done
        except Exception:
            logger.exception(
                "employer_code.isolated_execution_failure",
                extra={"execution_id": str(work.id), "attempt": work.attempt_count},
            )
            done = self._requeue(work, "trusted_execution_error")
            if done:
                self.queue.delete_message(message.receipt_handle)
            return done
        finally:
            if handle is not None and cleanup_permitted:
                self.sandbox.cleanup(handle)

    def run_forever(self) -> None:
        while True:
            self.publish_outbox_once()
            messages = self.queue.receive_messages(
                maximum=1, wait_seconds=20, visibility_timeout=90,
            )
            for message in messages:
                self.process_message(message)


def main() -> None:
    database_url = os.environ["RIGOR_EXECUTOR_DATABASE_URL"]
    queue_url = os.environ["RIGOR_EMPLOYER_EXECUTION_QUEUE_URL"]
    region = os.environ.get("AWS_REGION", "us-east-1")
    worker_id = f"employer:{socket.gethostname()}:{os.getpid()}"
    engine = create_engine(database_url, pool_pre_ping=True)
    queue = SqsJsonClient(queue_url=queue_url, region=region)
    sandbox = KubernetesSandboxExecutor(KubernetesApiConfig.discover())
    EmployerCodeWorker(
        engine=engine, queue=queue, sandbox=sandbox, worker_id=worker_id,
    ).run_forever()


if __name__ == "__main__":
    main()
