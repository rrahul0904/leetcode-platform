from __future__ import annotations

import json
import logging
import os
import socket
import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import Connection, Engine, create_engine, text

from .execution_claims import ExecutionClaimRepository, ExpiredExecutionLease
from .execution_domain import ExecutionRepository, ExecutionStatus
from .execution_events import (
    ExecutionCancelRequestedEvent,
    ExecutionRequestedEvent,
    parse_execution_queue_event,
)
from .execution_kubernetes import (
    KubernetesApiConfig,
    KubernetesSandboxExecutor,
    SandboxHandle,
    SandboxObservation,
)
from .execution_publisher import publish_outbox_batch
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
from .execution_sqs import SqsExecutionQueuePublisher, SqsJsonClient, SqsReceivedMessage
from .execution_submission import finalize_submission

logger = logging.getLogger("rigor.execution-controller")


@dataclass(frozen=True)
class ExecutionControllerSettings:
    database_url: str
    queue_url: str
    aws_region: str
    worker_id: str
    lease_seconds: int = 60
    reconciliation_limit: int = 50
    outbox_batch_size: int = 25
    receive_wait_seconds: int = 20
    receive_visibility_seconds: int = 90
    sandbox_poll_seconds: float = 0.5

    @classmethod
    def discover(cls) -> ExecutionControllerSettings:
        database_url = os.getenv("RIGOR_EXECUTOR_DATABASE_URL", "")
        queue_url = os.getenv("RIGOR_EXECUTION_QUEUE_URL", "")
        region = os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION") or ""
        if not database_url:
            raise RuntimeError("RIGOR_EXECUTOR_DATABASE_URL is required.")
        if not queue_url:
            raise RuntimeError("RIGOR_EXECUTION_QUEUE_URL is required.")
        if not region:
            raise RuntimeError("AWS_REGION is required.")
        worker_id = os.getenv(
            "RIGOR_EXECUTION_WORKER_ID",
            f"{socket.gethostname()}:{os.getpid()}",
        )
        return cls(
            database_url=database_url,
            queue_url=queue_url,
            aws_region=region,
            worker_id=worker_id,
            lease_seconds=int(os.getenv("RIGOR_EXECUTION_LEASE_SECONDS", "60")),
            reconciliation_limit=int(os.getenv("RIGOR_EXECUTION_RECONCILIATION_LIMIT", "50")),
            outbox_batch_size=int(os.getenv("RIGOR_EXECUTION_OUTBOX_BATCH_SIZE", "25")),
            receive_wait_seconds=int(os.getenv("RIGOR_EXECUTION_RECEIVE_WAIT_SECONDS", "20")),
            receive_visibility_seconds=int(
                os.getenv("RIGOR_EXECUTION_VISIBILITY_SECONDS", "90")
            ),
            sandbox_poll_seconds=float(os.getenv("RIGOR_EXECUTION_POLL_SECONDS", "0.5")),
        )


def _positive_limit(limits: dict[str, object], key: str, default: int) -> int:
    value = limits.get(key)
    if isinstance(value, int) and not isinstance(value, bool):
        return value if value > 0 else default
    if isinstance(value, str):
        try:
            parsed = int(value)
        except ValueError:
            return default
        return parsed if parsed > 0 else default
    return default


class ExecutionController:
    def __init__(
        self,
        *,
        settings: ExecutionControllerSettings,
        engine: Engine,
        queue: SqsJsonClient,
        sandbox: KubernetesSandboxExecutor,
    ) -> None:
        self.settings = settings
        self.engine = engine
        self.queue = queue
        self.publisher = SqsExecutionQueuePublisher(queue)
        self.sandbox = sandbox

    @classmethod
    def discover(cls) -> ExecutionController:
        settings = ExecutionControllerSettings.discover()
        engine = create_engine(
            settings.database_url,
            pool_pre_ping=True,
            pool_size=5,
            max_overflow=5,
        )
        queue = SqsJsonClient(queue_url=settings.queue_url, region=settings.aws_region)
        sandbox = KubernetesSandboxExecutor(KubernetesApiConfig.discover())
        return cls(settings=settings, engine=engine, queue=queue, sandbox=sandbox)

    def publish_outbox_once(self) -> int:
        with self.engine.begin() as connection:
            result = publish_outbox_batch(
                connection,
                self.publisher,
                limit=self.settings.outbox_batch_size,
            )
        if result.claimed:
            logger.info(
                "execution.outbox_batch",
                extra={
                    "claimed": result.claimed,
                    "published": result.published,
                    "failed": result.failed,
                },
            )
        return result.published

    def process_message(self, message: SqsReceivedMessage) -> bool:
        try:
            raw: object = json.loads(message.body)
            event = parse_execution_queue_event(raw)
        except (ValueError, json.JSONDecodeError) as exc:
            logger.error(
                "execution.queue_invalid_event",
                extra={"message_id": message.message_id, "error": exc.__class__.__name__},
            )
            # Leave poison deliveries for the configured SQS redrive policy.
            return False

        if isinstance(event, ExecutionCancelRequestedEvent):
            self._process_cancel(event)
            self.queue.delete_message(message.receipt_handle)
            return True

        self.queue.change_message_visibility(
            message.receipt_handle,
            self.settings.receive_visibility_seconds,
        )
        acknowledged = self._process_requested(event, message)
        if acknowledged:
            self.queue.delete_message(message.receipt_handle)
        return acknowledged

    def _process_requested(
        self,
        event: ExecutionRequestedEvent,
        message: SqsReceivedMessage,
    ) -> bool:
        lease_deadline = datetime.now(UTC) + timedelta(seconds=self.settings.lease_seconds)
        with self.engine.begin() as connection:
            claim = ExecutionClaimRepository(connection).claim_for_dispatch(
                event.execution_id,
                worker_id=self.settings.worker_id,
                lease_expires_at=lease_deadline,
            )
            if claim is None:
                # At-least-once redelivery is expected. If the durable aggregate
                # exists, another worker already claimed it or it is terminal.
                return self._execution_status(connection, event.execution_id) is not None
            package = load_dispatch_package(connection, event.execution_id)

        if package.language != "python":
            self._persist_infrastructure_failure(
                package,
                error_category="unsupported_execution_language",
                candidate_message="This runtime is not available in the production executor yet.",
            )
            return True

        profile_name = str(package.limits.get("profile") or "python-small")
        handle = self.sandbox.create_python_execution(
            execution_id=package.execution_id,
            request_payload=sandbox_request(package),
            profile_name=profile_name,
        )
        with self.engine.begin() as connection:
            running = ExecutionClaimRepository(connection).mark_running(
                package.execution_id,
                worker_id=self.settings.worker_id,
                kubernetes_namespace=handle.namespace,
                kubernetes_job_name=handle.job_name,
            )
        if not running:
            # This worker created the idempotent attempt but no longer owns the
            # durable claim. Cancellation is the normal path here.
            self.sandbox.cleanup(handle)
            return True

        terminal = self._monitor(package, handle, message)
        if terminal:
            # Never delete a Job after losing the lease: another controller may
            # have adopted it. Terminal owners can clean up idempotently.
            self.sandbox.cleanup(handle)
        return terminal

    def _monitor(
        self,
        package: DispatchPackage,
        handle: SandboxHandle,
        message: SqsReceivedMessage,
    ) -> bool:
        deadline_seconds = _positive_limit(package.limits, "job_deadline_seconds", 30)
        deadline = time.monotonic() + deadline_seconds + 10
        renew_after = max(5, self.settings.lease_seconds // 2)
        next_renewal = time.monotonic() + renew_after

        while True:
            observation = self.sandbox.observe(handle)
            if observation.state in {"SUCCEEDED", "FAILED"}:
                if observation.reason == "DeadlineExceeded" and not observation.logs:
                    self._persist_timeout(package)
                    return True
                return self._persist_observation(package, observation)
            if observation.state == "MISSING":
                self._persist_infrastructure_failure(
                    package,
                    error_category="sandbox_missing",
                    candidate_message="The isolated execution environment became unavailable.",
                )
                return True
            if time.monotonic() >= deadline:
                self._persist_timeout(package)
                return True
            if time.monotonic() >= next_renewal:
                if not self._renew_execution_lease(package.execution_id):
                    logger.warning(
                        "execution.lease_lost",
                        extra={"execution_id": str(package.execution_id)},
                    )
                    return False
                self.queue.change_message_visibility(
                    message.receipt_handle,
                    self.settings.receive_visibility_seconds,
                )
                next_renewal = time.monotonic() + renew_after
            time.sleep(self.settings.sandbox_poll_seconds)

    def _renew_execution_lease(self, execution_id: UUID) -> bool:
        renewed_until = datetime.now(UTC) + timedelta(seconds=self.settings.lease_seconds)
        with self.engine.begin() as connection:
            return ExecutionClaimRepository(connection).renew_lease(
                execution_id,
                worker_id=self.settings.worker_id,
                lease_expires_at=renewed_until,
            )

    def _persist_observation(
        self,
        package: DispatchPackage,
        observation: SandboxObservation,
    ) -> bool:
        if not observation.logs:
            self._persist_infrastructure_failure(
                package,
                error_category="runner_result_unavailable",
                candidate_message="The isolated runner did not return a usable result.",
            )
            return True
        try:
            sandbox_result = parse_runner_result(
                observation.logs,
                execution_id=package.execution_id,
            )
            with self.engine.begin() as connection:
                expected = load_expected_tests(
                    connection,
                    question_version_id=package.question_version_id,
                )
                projection = trusted_compare(sandbox_result, expected)
                terminal = persist_terminal_result(
                    connection,
                    execution_id=package.execution_id,
                    projection=projection,
                )
                if terminal == projection.execution_status:
                    finalize_submission(connection, package=package, projection=projection)
        except TrustedResultError as exc:
            self._persist_infrastructure_failure(
                package,
                error_category="trusted_result_validation_failed",
                candidate_message="Execution results could not be validated safely.",
            )
            logger.error(
                "execution.result_validation_failed",
                extra={
                    "execution_id": str(package.execution_id),
                    "error": exc.__class__.__name__,
                },
            )
        return True

    def _persist_timeout(self, package: DispatchPackage) -> None:
        timeout_seconds = _positive_limit(package.limits, "execution_timeout_seconds", 10)
        projection = TrustedExecutionProjection(
            execution_status=ExecutionStatus.timeout,
            runtime_ms=timeout_seconds * 1000,
            exit_code=124,
            error_category="timeout",
            public_results=[],
            hidden_total=0,
            hidden_passed=0,
            stdout="",
            stderr="",
            candidate_message="Execution exceeded the configured time limit.",
        )
        self._persist_projection(package, projection)

    def _persist_infrastructure_failure(
        self,
        package: DispatchPackage,
        *,
        error_category: str,
        candidate_message: str,
    ) -> None:
        projection = TrustedExecutionProjection(
            execution_status=ExecutionStatus.failed,
            runtime_ms=0,
            exit_code=1,
            error_category=error_category,
            public_results=[],
            hidden_total=0,
            hidden_passed=0,
            stdout="",
            stderr="",
            candidate_message=candidate_message,
        )
        self._persist_projection(package, projection)

    def _persist_projection(
        self,
        package: DispatchPackage,
        projection: TrustedExecutionProjection,
    ) -> None:
        with self.engine.begin() as connection:
            terminal = persist_terminal_result(
                connection,
                execution_id=package.execution_id,
                projection=projection,
            )
            if terminal == projection.execution_status:
                finalize_submission(connection, package=package, projection=projection)

    def _process_cancel(self, event: ExecutionCancelRequestedEvent) -> None:
        with self.engine.begin() as connection:
            row = (
                connection.execute(
                    text(
                        """
                        SELECT kubernetes_namespace, kubernetes_job_name
                        FROM execution_requests
                        WHERE id=:execution_id
                        """
                    ),
                    {"execution_id": event.execution_id},
                )
                .mappings()
                .one_or_none()
            )
        if row is None:
            return
        namespace = str(row["kubernetes_namespace"] or self.sandbox.config.namespace)
        job_name = str(row["kubernetes_job_name"] or f"execution-{event.execution_id}")
        self.sandbox.cleanup(
            SandboxHandle(
                execution_id=event.execution_id,
                namespace=namespace,
                job_name=job_name,
                input_secret_name=f"input-{job_name}",
                network_policy_name=f"deny-{job_name}",
            )
        )

    @staticmethod
    def _execution_status(
        connection: Connection,
        execution_id: UUID,
    ) -> ExecutionStatus | None:
        try:
            return ExecutionRepository(connection).get(execution_id).status
        except Exception:
            return None

    def reconcile_once(self) -> int:
        with self.engine.begin() as connection:
            expired = ExecutionClaimRepository(connection).expired_leases(
                limit=self.settings.reconciliation_limit
            )
        repaired = 0
        for lease in expired:
            try:
                repaired += int(self._reconcile_lease(lease))
            except Exception as exc:
                logger.exception(
                    "execution.reconciliation_failed",
                    extra={
                        "execution_id": str(lease.execution_id),
                        "error": exc.__class__.__name__,
                    },
                )
        return repaired

    def _reconcile_lease(self, lease: ExpiredExecutionLease) -> bool:
        namespace = lease.kubernetes_namespace or self.sandbox.config.namespace
        job_name = lease.kubernetes_job_name or f"execution-{lease.execution_id}"
        handle = SandboxHandle(
            execution_id=lease.execution_id,
            namespace=namespace,
            job_name=job_name,
            input_secret_name=f"input-{job_name}",
            network_policy_name=f"deny-{job_name}",
        )
        observation = self.sandbox.observe(handle)
        package = self._reacquire_expired_execution(lease, observation, namespace, job_name)
        if package is None:
            return False

        if observation.state in {"SUCCEEDED", "FAILED"}:
            terminal = self._persist_observation(package, observation)
            if terminal:
                self.sandbox.cleanup(handle)
            return terminal
        if observation.state == "MISSING":
            self._persist_infrastructure_failure(
                package,
                error_category="sandbox_missing_after_lease_expiry",
                candidate_message="The isolated execution environment was lost before completion.",
            )
            self.sandbox.cleanup(handle)
            return True

        # The Job still exists and the new lease now owns recovery. A later
        # reconciliation pass will inspect it after this bounded lease expires.
        return True

    def _reacquire_expired_execution(
        self,
        lease: ExpiredExecutionLease,
        observation: SandboxObservation,
        namespace: str,
        job_name: str,
    ) -> DispatchPackage | None:
        new_deadline = datetime.now(UTC) + timedelta(seconds=self.settings.lease_seconds)
        with self.engine.begin() as connection:
            reacquired = connection.execute(
                text(
                    """
                    UPDATE execution_requests
                    SET lease_owner=:worker_id,
                        lease_expires_at=:lease_expires_at
                    WHERE id=:execution_id
                      AND state::text=:state
                      AND lease_expires_at < CURRENT_TIMESTAMP
                    RETURNING id
                    """
                ),
                {
                    "execution_id": lease.execution_id,
                    "state": lease.status.value,
                    "worker_id": self.settings.worker_id,
                    "lease_expires_at": new_deadline,
                },
            ).scalar_one_or_none()
            if reacquired is None:
                return None
            package = load_dispatch_package(connection, lease.execution_id)
            if lease.status is ExecutionStatus.dispatching and observation.state != "MISSING":
                marked_running = ExecutionClaimRepository(connection).mark_running(
                    lease.execution_id,
                    worker_id=self.settings.worker_id,
                    kubernetes_namespace=namespace,
                    kubernetes_job_name=job_name,
                )
                if not marked_running:
                    return None
            return package

    def run_forever(self) -> None:
        logger.info("execution.controller_started", extra={"worker_id": self.settings.worker_id})
        last_reconciliation = 0.0
        while True:
            try:
                self.publish_outbox_once()
                now = time.monotonic()
                if now - last_reconciliation >= 30:
                    self.reconcile_once()
                    last_reconciliation = now
                messages = self.queue.receive_messages(
                    maximum=10,
                    wait_seconds=self.settings.receive_wait_seconds,
                    visibility_timeout=self.settings.receive_visibility_seconds,
                )
                for message in messages:
                    try:
                        self.process_message(message)
                    except Exception as exc:
                        logger.exception(
                            "execution.message_failed",
                            extra={
                                "message_id": message.message_id,
                                "error": exc.__class__.__name__,
                            },
                        )
            except Exception as exc:
                logger.exception(
                    "execution.controller_iteration_failed",
                    extra={"error": exc.__class__.__name__},
                )
                time.sleep(1.0)


def main() -> int:
    logging.basicConfig(level=os.getenv("RIGOR_LOG_LEVEL", "INFO"))
    controller = ExecutionController.discover()
    try:
        controller.run_forever()
    finally:
        controller.engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
