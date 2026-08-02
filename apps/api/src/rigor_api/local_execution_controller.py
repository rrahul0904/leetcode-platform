from __future__ import annotations

import json
import logging
import os
import socket
import time
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from threading import Lock
from typing import cast
from urllib import error, request
from uuid import UUID

from sqlalchemy import Engine, create_engine, text

from .execution_controller import ExecutionController, ExecutionControllerSettings
from .execution_kubernetes import (
    KubernetesSandboxExecutor,
    SandboxHandle,
    SandboxObservation,
)
from .execution_results import RESULT_PREFIX
from .execution_sqs import SqsJsonClient, SqsReceivedMessage

logger = logging.getLogger("rigor.local-execution-controller")
MAX_QUEUE_BODY_BYTES = 1024 * 1024
MAX_RUNNER_RESPONSE_BYTES = 512 * 1024


class LocalExecutionTransportError(RuntimeError):
    pass


class LocalExecutionQueueClient:
    """PostgreSQL-backed SQS-compatible queue for the local Docker controller."""

    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    @staticmethod
    def _validate_body(body: str) -> None:
        if not body or len(body.encode("utf-8")) > MAX_QUEUE_BODY_BYTES:
            raise LocalExecutionTransportError("Local execution queue body is invalid.")
        try:
            decoded: object = json.loads(body)
        except json.JSONDecodeError as exc:
            raise LocalExecutionTransportError(
                "Local execution queue body must be valid JSON."
            ) from exc
        if not isinstance(decoded, dict):
            raise LocalExecutionTransportError(
                "Local execution queue body must be a JSON object."
            )

    def send_message(self, body: str) -> str:
        self._validate_body(body)
        with self.engine.begin() as connection:
            message_id = connection.execute(
                text(
                    """
                    INSERT INTO local_execution_queue (body)
                    VALUES (:body)
                    RETURNING id
                    """
                ),
                {"body": body},
            ).scalar_one()
        return str(message_id)

    def receive_messages(
        self,
        *,
        maximum: int = 10,
        wait_seconds: int = 20,
        visibility_timeout: int = 60,
    ) -> list[SqsReceivedMessage]:
        if not 1 <= maximum <= 10:
            raise ValueError("maximum must be between 1 and 10")
        if visibility_timeout < 1:
            raise ValueError("visibility_timeout must be positive")
        with self.engine.begin() as connection:
            rows = (
                connection.execute(
                    text(
                        """
                        WITH selected AS (
                          SELECT id
                          FROM local_execution_queue
                          WHERE visible_at <= CURRENT_TIMESTAMP
                          ORDER BY created_at, id
                          FOR UPDATE SKIP LOCKED
                          LIMIT :maximum
                        )
                        UPDATE local_execution_queue queue
                        SET receipt_handle=gen_random_uuid(),
                            visible_at=CURRENT_TIMESTAMP
                              + make_interval(secs => :visibility_timeout),
                            receive_count=queue.receive_count + 1,
                            updated_at=CURRENT_TIMESTAMP
                        FROM selected
                        WHERE queue.id=selected.id
                        RETURNING queue.id, queue.receipt_handle, queue.body
                        """
                    ),
                    {
                        "maximum": maximum,
                        "visibility_timeout": visibility_timeout,
                    },
                )
                .mappings()
                .all()
            )
        if not rows and wait_seconds > 0:
            time.sleep(min(float(wait_seconds), 1.0))
        return [
            SqsReceivedMessage(
                message_id=str(row["id"]),
                receipt_handle=str(row["receipt_handle"]),
                body=str(row["body"]),
            )
            for row in rows
        ]

    def delete_message(self, receipt_handle: str) -> None:
        with self.engine.begin() as connection:
            connection.execute(
                text(
                    """
                    DELETE FROM local_execution_queue
                    WHERE receipt_handle=:receipt_handle
                    """
                ),
                {"receipt_handle": receipt_handle},
            )

    def change_message_visibility(self, receipt_handle: str, timeout_seconds: int) -> None:
        if timeout_seconds < 0:
            raise ValueError("timeout_seconds must be non-negative")
        with self.engine.begin() as connection:
            connection.execute(
                text(
                    """
                    UPDATE local_execution_queue
                    SET visible_at=CURRENT_TIMESTAMP
                          + make_interval(secs => :timeout_seconds),
                        updated_at=CURRENT_TIMESTAMP
                    WHERE receipt_handle=:receipt_handle
                    """
                ),
                {
                    "receipt_handle": receipt_handle,
                    "timeout_seconds": timeout_seconds,
                },
            )

    def depth(self) -> int:
        with self.engine.connect() as connection:
            return int(
                connection.execute(text("SELECT count(*) FROM local_execution_queue")).scalar_one()
            )


@dataclass(frozen=True)
class LocalSandboxConfig:
    namespace: str = "local-docker"


class LocalHttpSandboxExecutor:
    """Dispatch runner requests to dedicated local Docker services.

    Python execution still creates a restricted subprocess per test inside the
    dedicated runner container. SQL execution uses a separate PostgreSQL service
    that contains no application data or application credentials. This is a
    development boundary and is intentionally not described as gVisor-equivalent.
    """

    def __init__(
        self,
        *,
        python_url: str,
        sql_url: str,
        maximum_parallel: int = 4,
    ) -> None:
        if not python_url.startswith("http://") or not sql_url.startswith("http://"):
            raise LocalExecutionTransportError(
                "Local runner URLs must use the internal HTTP Docker network."
            )
        self.config = LocalSandboxConfig()
        self.python_url = python_url.rstrip("/")
        self.sql_url = sql_url.rstrip("/")
        self._executor = ThreadPoolExecutor(
            max_workers=max(1, min(maximum_parallel, 16)),
            thread_name_prefix="rigor-local-runner",
        )
        self._futures: dict[UUID, Future[dict[str, object]]] = {}
        self._attempts: dict[UUID, int] = {}
        self._lock = Lock()

    @staticmethod
    def _invoke(
        url: str,
        payload: dict[str, object],
        timeout_seconds: int,
    ) -> dict[str, object]:
        encoded = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode(
            "utf-8"
        )
        if len(encoded) > MAX_QUEUE_BODY_BYTES:
            raise LocalExecutionTransportError("Runner request exceeds the local limit.")
        runner_request = request.Request(
            f"{url}/run",
            data=encoded,
            headers={
                "Content-Type": "application/json",
                "X-Rigor-Timeout-Seconds": str(timeout_seconds),
            },
            method="POST",
        )
        try:
            with request.urlopen(
                runner_request,
                timeout=float(timeout_seconds + 10),
            ) as response:
                raw = response.read(MAX_RUNNER_RESPONSE_BYTES + 1)
        except error.HTTPError as exc:
            detail = exc.read(16 * 1024).decode("utf-8", errors="replace")
            raise LocalExecutionTransportError(
                f"Runner returned HTTP {exc.code}: {detail[:1000]}"
            ) from exc
        except OSError as exc:
            raise LocalExecutionTransportError("Local runner transport failed.") from exc
        if len(raw) > MAX_RUNNER_RESPONSE_BYTES:
            raise LocalExecutionTransportError("Runner response exceeds the local limit.")
        try:
            decoded: object = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise LocalExecutionTransportError("Runner response is malformed JSON.") from exc
        if not isinstance(decoded, dict):
            raise LocalExecutionTransportError("Runner response is not a JSON object.")
        return cast(dict[str, object], decoded)

    def _create(
        self,
        *,
        execution_id: UUID,
        request_payload: dict[str, object],
        url: str,
        profile_name: str,
    ) -> SandboxHandle:
        limits = {
            "python-small": 10,
            "sql-small": 15,
        }
        timeout_seconds = limits.get(profile_name, 10)
        future = self._executor.submit(
            self._invoke,
            url,
            request_payload,
            timeout_seconds,
        )
        with self._lock:
            self._futures[execution_id] = future
            attempt = request_payload.get("attempt")
            self._attempts[execution_id] = (
                attempt if isinstance(attempt, int) and not isinstance(attempt, bool) else 0
            )
        job_name = f"local-{execution_id}"
        return SandboxHandle(
            execution_id=execution_id,
            namespace=self.config.namespace,
            job_name=job_name,
            input_secret_name=f"input-{job_name}",
            network_policy_name=f"deny-{job_name}",
        )

    def create_python_execution(
        self,
        *,
        execution_id: UUID,
        request_payload: dict[str, object],
        profile_name: str,
    ) -> SandboxHandle:
        return self._create(
            execution_id=execution_id,
            request_payload=request_payload,
            url=self.python_url,
            profile_name=profile_name,
        )

    def create_sql_execution(
        self,
        *,
        execution_id: UUID,
        request_payload: dict[str, object],
        profile_name: str,
    ) -> SandboxHandle:
        return self._create(
            execution_id=execution_id,
            request_payload=request_payload,
            url=self.sql_url,
            profile_name=profile_name,
        )

    def observe(self, handle: SandboxHandle) -> SandboxObservation:
        with self._lock:
            future = self._futures.get(handle.execution_id)
            attempt = self._attempts.get(handle.execution_id, 0)
        if future is None:
            return SandboxObservation(state="MISSING")
        if not future.done():
            return SandboxObservation(state="RUNNING")
        try:
            result = future.result()
        except Exception as exc:
            result = {
                "schema_version": 1,
                "execution_id": str(handle.execution_id),
                "attempt": max(1, attempt),
                "status": "FAILED",
                "runtime_ms": 0,
                "exit_code": 3,
                "tests": [],
                "stdout": "",
                "stderr": "",
                "error_category": "runner_infrastructure_error",
            }
            logger.warning(
                "local_execution.runner_failed",
                extra={
                    "component": "local-execution-controller",
                    "event": "runner_failed",
                    "execution_id": str(handle.execution_id),
                    "error": exc.__class__.__name__,
                },
            )
        status = str(result.get("status") or "FAILED")
        return SandboxObservation(
            state="SUCCEEDED" if status == "COMPLETED" else "FAILED",
            logs=RESULT_PREFIX
            + json.dumps(result, separators=(",", ":"), ensure_ascii=False),
            reason=str(result.get("error_category") or "") or None,
        )

    def cleanup(self, handle: SandboxHandle) -> None:
        with self._lock:
            future = self._futures.pop(handle.execution_id, None)
            self._attempts.pop(handle.execution_id, None)
        if future is not None and not future.done():
            future.cancel()


class LocalExecutionController(ExecutionController):
    queue: LocalExecutionQueueClient

    def heartbeat_once(self) -> None:
        queue_depth = self.queue.depth()
        with self.engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO local_execution_controller_status (
                      controller_key, worker_id, heartbeat_at, queue_depth
                    )
                    VALUES ('local', :worker_id, CURRENT_TIMESTAMP, :queue_depth)
                    ON CONFLICT (controller_key) DO UPDATE
                    SET worker_id=EXCLUDED.worker_id,
                        heartbeat_at=EXCLUDED.heartbeat_at,
                        queue_depth=EXCLUDED.queue_depth
                    """
                ),
                {
                    "worker_id": self.settings.worker_id,
                    "queue_depth": queue_depth,
                },
            )

    def run_forever(self) -> None:
        logger.info(
            "local_execution.controller_started",
            extra={
                "component": "local-execution-controller",
                "event": "controller_started",
                "worker_id": self.settings.worker_id,
            },
        )
        last_reconciliation = 0.0
        while True:
            try:
                self.heartbeat_once()
                self.publish_outbox_once()
                now = time.monotonic()
                if now - last_reconciliation >= 10:
                    self.reconcile_once()
                    last_reconciliation = now
                messages = self.queue.receive_messages(
                    maximum=10,
                    wait_seconds=1,
                    visibility_timeout=self.settings.receive_visibility_seconds,
                )
                for message in messages:
                    try:
                        self.process_message(message)
                    except Exception as exc:
                        logger.exception(
                            "local_execution.message_failed",
                            extra={
                                "component": "local-execution-controller",
                                "event": "message_failed",
                                "message_id": message.message_id,
                                "error": exc.__class__.__name__,
                            },
                        )
            except Exception as exc:
                logger.exception(
                    "local_execution.controller_iteration_failed",
                    extra={
                        "component": "local-execution-controller",
                        "event": "controller_iteration_failed",
                        "error": exc.__class__.__name__,
                    },
                )
                time.sleep(1.0)


def discover() -> LocalExecutionController:
    database_url = os.getenv("RIGOR_EXECUTOR_DATABASE_URL", "")
    if not database_url:
        raise RuntimeError("RIGOR_EXECUTOR_DATABASE_URL is required.")
    worker_id = os.getenv(
        "RIGOR_EXECUTION_WORKER_ID",
        f"local:{socket.gethostname()}:{os.getpid()}",
    )
    settings = ExecutionControllerSettings(
        database_url=database_url,
        queue_url="postgresql://local-execution-queue",
        aws_region="local",
        worker_id=worker_id,
        lease_seconds=int(os.getenv("RIGOR_EXECUTION_LEASE_SECONDS", "60")),
        reconciliation_limit=int(
            os.getenv("RIGOR_EXECUTION_RECONCILIATION_LIMIT", "50")
        ),
        outbox_batch_size=int(os.getenv("RIGOR_EXECUTION_OUTBOX_BATCH_SIZE", "25")),
        receive_wait_seconds=1,
        receive_visibility_seconds=int(
            os.getenv("RIGOR_EXECUTION_VISIBILITY_SECONDS", "90")
        ),
        sandbox_poll_seconds=float(os.getenv("RIGOR_EXECUTION_POLL_SECONDS", "0.1")),
        max_attempts=int(os.getenv("RIGOR_EXECUTION_MAX_ATTEMPTS", "3")),
        stale_queued_seconds=int(
            os.getenv("RIGOR_EXECUTION_STALE_QUEUED_SECONDS", "30")
        ),
    )
    engine = create_engine(
        database_url,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=5,
    )
    queue = LocalExecutionQueueClient(engine)
    sandbox = LocalHttpSandboxExecutor(
        python_url=os.getenv(
            "RIGOR_LOCAL_PYTHON_RUNNER_URL",
            "http://python-runner:8081",
        ),
        sql_url=os.getenv(
            "RIGOR_LOCAL_SQL_RUNNER_URL",
            "http://sql-runner:8082",
        ),
        maximum_parallel=int(os.getenv("RIGOR_LOCAL_EXECUTION_PARALLELISM", "4")),
    )
    controller = LocalExecutionController(
        settings=settings,
        engine=engine,
        queue=cast(SqsJsonClient, queue),
        sandbox=cast(KubernetesSandboxExecutor, sandbox),
    )
    controller.queue = queue
    return controller


def main() -> int:
    logging.basicConfig(level=os.getenv("RIGOR_LOG_LEVEL", "INFO"))
    controller = discover()
    try:
        controller.run_forever()
    finally:
        controller.engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
