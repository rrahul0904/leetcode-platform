from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from hashlib import sha256
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import Connection, text


class ExecutionStatus(StrEnum):
    queued = "QUEUED"
    dispatching = "DISPATCHING"
    running = "RUNNING"
    completed = "COMPLETED"
    failed = "FAILED"
    timeout = "TIMEOUT"
    cancelled = "CANCELLED"


class ExecutionType(StrEnum):
    run = "RUN"
    submit = "SUBMIT"


class ExecutionTransitionError(ValueError):
    pass


class ExecutionNotFoundError(LookupError):
    pass


class IdempotencyConflictError(ValueError):
    pass


TERMINAL_EXECUTION_STATUSES = frozenset(
    {
        ExecutionStatus.completed,
        ExecutionStatus.failed,
        ExecutionStatus.timeout,
        ExecutionStatus.cancelled,
    }
)

LEGAL_EXECUTION_TRANSITIONS: dict[ExecutionStatus, frozenset[ExecutionStatus]] = {
    ExecutionStatus.queued: frozenset(
        {
            ExecutionStatus.dispatching,
            ExecutionStatus.cancelled,
        }
    ),
    ExecutionStatus.dispatching: frozenset(
        {
            ExecutionStatus.running,
            ExecutionStatus.failed,
            ExecutionStatus.cancelled,
        }
    ),
    ExecutionStatus.running: frozenset(
        {
            ExecutionStatus.completed,
            ExecutionStatus.failed,
            ExecutionStatus.timeout,
            ExecutionStatus.cancelled,
        }
    ),
    ExecutionStatus.completed: frozenset(),
    ExecutionStatus.failed: frozenset(),
    ExecutionStatus.timeout: frozenset(),
    ExecutionStatus.cancelled: frozenset(),
}


LEGACY_STATUS_MAP: dict[str, ExecutionStatus] = {
    "PASSED": ExecutionStatus.completed,
    "ERROR": ExecutionStatus.failed,
    "TIMED_OUT": ExecutionStatus.timeout,
}


@dataclass(frozen=True)
class QueuedExecution:
    execution_id: UUID
    submission_id: UUID | None
    status: ExecutionStatus
    execution_type: ExecutionType
    runtime: str
    created_at: datetime
    trace_id: str
    duplicate: bool = False


@dataclass(frozen=True)
class ExecutionSnapshot:
    execution_id: UUID
    submission_id: UUID | None
    status: ExecutionStatus
    execution_type: ExecutionType
    runtime: str
    created_at: datetime
    queued_at: datetime
    dispatch_started_at: datetime | None
    running_at: datetime | None
    completed_at: datetime | None
    runtime_ms: int | None
    error_category: str | None
    trace_id: str


def normalize_execution_status(value: str) -> ExecutionStatus:
    mapped = LEGACY_STATUS_MAP.get(value)
    if mapped is not None:
        return mapped
    return ExecutionStatus(value)


def validate_execution_transition(
    current: ExecutionStatus,
    target: ExecutionStatus,
) -> None:
    if target not in LEGAL_EXECUTION_TRANSITIONS[current]:
        raise ExecutionTransitionError(
            f"Illegal execution transition: {current.value} -> {target.value}"
        )


def execution_request_hash(
    *,
    execution_type: ExecutionType,
    practice_session_id: UUID,
    question_version_id: UUID,
    runtime: str,
    source_code: str,
) -> str:
    canonical = json.dumps(
        {
            "execution_type": execution_type.value,
            "practice_session_id": str(practice_session_id),
            "question_version_id": str(question_version_id),
            "runtime": runtime,
            "source_code": source_code,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return sha256(canonical.encode("utf-8")).hexdigest()


def execution_requested_event(
    *,
    execution_id: UUID,
    requested_at: datetime,
    trace_id: str,
    attempt: int = 1,
) -> dict[str, object]:
    return {
        "schema_version": 1,
        "event_type": "execution.requested",
        "execution_id": str(execution_id),
        "attempt": attempt,
        "requested_at": requested_at.astimezone(UTC).isoformat(),
        "trace_id": trace_id,
    }


class ExecutionRepository:
    """Durable execution aggregate persisted inside the caller's transaction.

    Candidate source is stored separately from the queue event. The transactional
    outbox carries only an execution identifier and bounded metadata.
    """

    def __init__(self, connection: Connection) -> None:
        self._connection = connection

    def create_queued(
        self,
        *,
        execution_type: ExecutionType,
        practice_session_id: UUID,
        submission_id: UUID | None,
        question_version_id: UUID,
        runtime: str,
        language: str,
        source_code: str,
        idempotency_key: str,
        trace_id: str,
        limits: dict[str, object],
        input_payload: dict[str, object] | None = None,
    ) -> QueuedExecution:
        request_hash = execution_request_hash(
            execution_type=execution_type,
            practice_session_id=practice_session_id,
            question_version_id=question_version_id,
            runtime=runtime,
            source_code=source_code,
        )
        existing = self._find_by_idempotency(idempotency_key)
        if existing is not None:
            if str(existing["request_hash"]) != request_hash:
                raise IdempotencyConflictError(
                    "The Idempotency-Key was already used for a different execution request."
                )
            return self._queued_from_row(existing, duplicate=True)

        execution_id = uuid4()
        requested_at = datetime.now(UTC)
        code_reference = f"db://execution-payloads/{execution_id}"

        row = (
            self._connection.execute(
                text(
                    """
                    INSERT INTO execution_requests (
                        id,
                        organization_id,
                        candidate_id,
                        practice_session_id,
                        submission_id,
                        question_version_id,
                        runtime,
                        adapter,
                        state,
                        idempotency_key,
                        source_hash,
                        request_hash,
                        limits,
                        queued_at,
                        execution_type,
                        language,
                        code_reference,
                        input_reference,
                        attempt_count,
                        trace_id
                    ) VALUES (
                        :execution_id,
                        NULLIF(current_setting('rigor.organization_id', true), '')::uuid,
                        NULLIF(current_setting('rigor.user_id', true), '')::uuid,
                        :practice_session_id,
                        :submission_id,
                        :question_version_id,
                        :runtime,
                        'KUBERNETES_JOB',
                        'QUEUED'::execution_state,
                        :idempotency_key,
                        :source_hash,
                        :request_hash,
                        CAST(:limits AS jsonb),
                        :queued_at,
                        :execution_type,
                        :language,
                        :code_reference,
                        NULL,
                        0,
                        :trace_id
                    )
                    ON CONFLICT (candidate_id, idempotency_key) DO NOTHING
                    RETURNING
                        id,
                        submission_id,
                        state::text AS state,
                        execution_type,
                        runtime,
                        created_at,
                        trace_id,
                        request_hash
                    """
                ),
                {
                    "execution_id": execution_id,
                    "practice_session_id": practice_session_id,
                    "submission_id": submission_id,
                    "question_version_id": question_version_id,
                    "runtime": runtime,
                    "idempotency_key": idempotency_key,
                    "source_hash": sha256(source_code.encode("utf-8")).hexdigest(),
                    "request_hash": request_hash,
                    "limits": json.dumps(limits, separators=(",", ":")),
                    "queued_at": requested_at,
                    "execution_type": execution_type.value,
                    "language": language,
                    "code_reference": code_reference,
                    "trace_id": trace_id,
                },
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            concurrent = self._find_by_idempotency(idempotency_key)
            if concurrent is None:
                raise RuntimeError("Execution idempotency conflict could not be resolved.")
            if str(concurrent["request_hash"]) != request_hash:
                raise IdempotencyConflictError(
                    "The Idempotency-Key was already used for a different execution request."
                )
            return self._queued_from_row(concurrent, duplicate=True)

        self._connection.execute(
            text(
                """
                INSERT INTO execution_payloads (
                    execution_request_id,
                    source_code,
                    input_payload
                ) VALUES (
                    :execution_id,
                    :source_code,
                    CAST(:input_payload AS jsonb)
                )
                """
            ),
            {
                "execution_id": execution_id,
                "source_code": source_code,
                "input_payload": json.dumps(input_payload or {}, separators=(",", ":")),
            },
        )
        self._append_event(
            execution_id=execution_id,
            status=ExecutionStatus.queued,
            details={"attempt": 0, "trace_id": trace_id},
        )
        event = execution_requested_event(
            execution_id=execution_id,
            requested_at=requested_at,
            trace_id=trace_id,
        )
        self._connection.execute(
            text(
                """
                INSERT INTO execution_outbox (
                    aggregate_type,
                    aggregate_id,
                    event_type,
                    dedupe_key,
                    payload,
                    created_at,
                    next_attempt_at
                ) VALUES (
                    'execution',
                    :execution_id,
                    'execution.requested',
                    :dedupe_key,
                    CAST(:payload AS jsonb),
                    :created_at,
                    :created_at
                )
                ON CONFLICT (dedupe_key) DO NOTHING
                """
            ),
            {
                "execution_id": execution_id,
                "dedupe_key": f"execution.requested:{execution_id}",
                "payload": json.dumps(event, separators=(",", ":")),
                "created_at": requested_at,
            },
        )
        return self._queued_from_row(row, duplicate=False)

    def get(self, execution_id: UUID) -> ExecutionSnapshot:
        row = (
            self._connection.execute(
                text(
                    """
                    SELECT
                        id,
                        submission_id,
                        state::text AS state,
                        execution_type,
                        runtime,
                        created_at,
                        queued_at,
                        dispatch_started_at,
                        running_at,
                        completed_at,
                        runtime_ms,
                        error_category,
                        trace_id
                    FROM execution_requests
                    WHERE id=:execution_id
                    """
                ),
                {"execution_id": execution_id},
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            raise ExecutionNotFoundError(str(execution_id))
        return ExecutionSnapshot(
            execution_id=UUID(str(row["id"])),
            submission_id=UUID(str(row["submission_id"])) if row["submission_id"] else None,
            status=normalize_execution_status(str(row["state"])),
            execution_type=ExecutionType(str(row["execution_type"])),
            runtime=str(row["runtime"]),
            created_at=row["created_at"],
            queued_at=row["queued_at"],
            dispatch_started_at=row["dispatch_started_at"],
            running_at=row["running_at"],
            completed_at=row["completed_at"],
            runtime_ms=int(row["runtime_ms"]) if row["runtime_ms"] is not None else None,
            error_category=str(row["error_category"]) if row["error_category"] else None,
            trace_id=str(row["trace_id"]),
        )

    def transition(
        self,
        execution_id: UUID,
        target: ExecutionStatus,
        *,
        details: dict[str, object] | None = None,
        lease_owner: str | None = None,
        lease_expires_at: datetime | None = None,
    ) -> ExecutionSnapshot:
        row = (
            self._connection.execute(
                text(
                    """
                    SELECT state::text AS state
                    FROM execution_requests
                    WHERE id=:execution_id
                    FOR UPDATE
                    """
                ),
                {"execution_id": execution_id},
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            raise ExecutionNotFoundError(str(execution_id))
        current = normalize_execution_status(str(row["state"]))
        validate_execution_transition(current, target)

        completed_at = datetime.now(UTC) if target in TERMINAL_EXECUTION_STATUSES else None
        self._connection.execute(
            text(
                """
                UPDATE execution_requests
                SET
                    state=CAST(:target AS execution_state),
                    dispatch_started_at=CASE
                        WHEN :target='DISPATCHING'
                        THEN COALESCE(dispatch_started_at, CURRENT_TIMESTAMP)
                        ELSE dispatch_started_at
                    END,
                    running_at=CASE
                        WHEN :target='RUNNING'
                        THEN COALESCE(running_at, CURRENT_TIMESTAMP)
                        ELSE running_at
                    END,
                    started_at=CASE
                        WHEN :target='RUNNING'
                        THEN COALESCE(started_at, CURRENT_TIMESTAMP)
                        ELSE started_at
                    END,
                    completed_at=COALESCE(:completed_at, completed_at),
                    lease_owner=:lease_owner,
                    lease_expires_at=:lease_expires_at
                WHERE id=:execution_id
                """
            ),
            {
                "execution_id": execution_id,
                "target": target.value,
                "completed_at": completed_at,
                "lease_owner": lease_owner,
                "lease_expires_at": lease_expires_at,
            },
        )
        self._append_event(
            execution_id=execution_id,
            status=target,
            details={
                "from": current.value,
                "to": target.value,
                **(details or {}),
            },
        )
        return self.get(execution_id)

    def cancel(self, execution_id: UUID, *, trace_id: str) -> ExecutionSnapshot:
        current = self.get(execution_id)
        if current.status == ExecutionStatus.cancelled:
            return current
        if current.status in TERMINAL_EXECUTION_STATUSES:
            raise ExecutionTransitionError(
                f"Cannot cancel terminal execution {current.status.value}."
            )

        cancelled = self.transition(
            execution_id,
            ExecutionStatus.cancelled,
            details={"reason": "candidate_requested", "trace_id": trace_id},
        )
        now = datetime.now(UTC)
        self._connection.execute(
            text(
                """
                INSERT INTO execution_outbox (
                    aggregate_type,
                    aggregate_id,
                    event_type,
                    dedupe_key,
                    payload,
                    created_at,
                    next_attempt_at
                ) VALUES (
                    'execution',
                    :execution_id,
                    'execution.cancel_requested',
                    :dedupe_key,
                    CAST(:payload AS jsonb),
                    :created_at,
                    :created_at
                )
                ON CONFLICT (dedupe_key) DO NOTHING
                """
            ),
            {
                "execution_id": execution_id,
                "dedupe_key": f"execution.cancel_requested:{execution_id}",
                "payload": json.dumps(
                    {
                        "schema_version": 1,
                        "event_type": "execution.cancel_requested",
                        "execution_id": str(execution_id),
                        "requested_at": now.isoformat(),
                        "trace_id": trace_id,
                    },
                    separators=(",", ":"),
                ),
                "created_at": now,
            },
        )
        return cancelled

    def _find_by_idempotency(self, idempotency_key: str) -> Any | None:
        return (
            self._connection.execute(
                text(
                    """
                    SELECT
                        id,
                        submission_id,
                        state::text AS state,
                        execution_type,
                        runtime,
                        created_at,
                        trace_id,
                        request_hash
                    FROM execution_requests
                    WHERE candidate_id=
                        NULLIF(current_setting('rigor.user_id', true), '')::uuid
                      AND idempotency_key=:idempotency_key
                    """
                ),
                {"idempotency_key": idempotency_key},
            )
            .mappings()
            .one_or_none()
        )

    @staticmethod
    def _queued_from_row(row: Any, *, duplicate: bool) -> QueuedExecution:
        return QueuedExecution(
            execution_id=UUID(str(row["id"])),
            submission_id=UUID(str(row["submission_id"])) if row["submission_id"] else None,
            status=normalize_execution_status(str(row["state"])),
            execution_type=ExecutionType(str(row["execution_type"])),
            runtime=str(row["runtime"]),
            created_at=row["created_at"],
            trace_id=str(row["trace_id"]),
            duplicate=duplicate,
        )

    def _append_event(
        self,
        *,
        execution_id: UUID,
        status: ExecutionStatus,
        details: dict[str, object],
    ) -> None:
        self._connection.execute(
            text(
                """
                INSERT INTO execution_events (
                    execution_request_id,
                    sequence_number,
                    state,
                    details
                )
                SELECT
                    :execution_id,
                    COALESCE(max(sequence_number), -1) + 1,
                    CAST(:state AS execution_state),
                    CAST(:details AS jsonb)
                FROM execution_events
                WHERE execution_request_id=:execution_id
                """
            ),
            {
                "execution_id": execution_id,
                "state": status.value,
                "details": json.dumps(details, separators=(",", ":")),
            },
        )
