from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import Connection, text

from .execution_domain import ExecutionStatus


@dataclass(frozen=True)
class ExecutionClaim:
    execution_id: UUID
    runtime: str
    execution_type: str
    language: str
    code_reference: str | None
    input_reference: str | None
    attempt_count: int
    lease_owner: str
    lease_expires_at: datetime
    trace_id: str


@dataclass(frozen=True)
class ExpiredExecutionLease:
    execution_id: UUID
    status: ExecutionStatus
    lease_owner: str | None
    lease_expires_at: datetime
    kubernetes_namespace: str | None
    kubernetes_job_name: str | None
    attempt_count: int


def validate_lease_deadline(value: datetime) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Lease deadline must be timezone-aware.")
    if value <= datetime.now(UTC):
        raise ValueError("Lease deadline must be in the future.")


class ExecutionClaimRepository:
    """Trusted-worker compare-and-set operations for execution ownership."""

    def __init__(self, connection: Connection) -> None:
        self._connection = connection

    def claim_for_dispatch(
        self,
        execution_id: UUID,
        *,
        worker_id: str,
        lease_expires_at: datetime,
    ) -> ExecutionClaim | None:
        validate_lease_deadline(lease_expires_at)
        row = (
            self._connection.execute(
                text(
                    """
                    UPDATE execution_requests
                    SET state='DISPATCHING'::execution_state,
                        lease_owner=:worker_id,
                        lease_expires_at=:lease_expires_at,
                        attempt_count=attempt_count + 1,
                        dispatch_started_at=COALESCE(
                            dispatch_started_at,
                            CURRENT_TIMESTAMP
                        )
                    WHERE id=:execution_id
                      AND state='QUEUED'::execution_state
                    RETURNING
                        id,
                        runtime,
                        execution_type,
                        language,
                        code_reference,
                        input_reference,
                        attempt_count,
                        lease_owner,
                        lease_expires_at,
                        trace_id
                    """
                ),
                {
                    "execution_id": execution_id,
                    "worker_id": worker_id,
                    "lease_expires_at": lease_expires_at,
                },
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            return None

        attempt_count = int(row["attempt_count"])
        self._append_event(
            execution_id,
            ExecutionStatus.dispatching,
            {
                "attempt": attempt_count,
                "lease_owner": worker_id,
                "lease_expires_at": lease_expires_at.isoformat(),
            },
        )
        return ExecutionClaim(
            execution_id=UUID(str(row["id"])),
            runtime=str(row["runtime"]),
            execution_type=str(row["execution_type"]),
            language=str(row["language"]),
            code_reference=str(row["code_reference"]) if row["code_reference"] else None,
            input_reference=str(row["input_reference"]) if row["input_reference"] else None,
            attempt_count=attempt_count,
            lease_owner=str(row["lease_owner"]),
            lease_expires_at=row["lease_expires_at"],
            trace_id=str(row["trace_id"]),
        )

    def mark_running(
        self,
        execution_id: UUID,
        *,
        worker_id: str,
        kubernetes_namespace: str,
        kubernetes_job_name: str,
    ) -> bool:
        row = (
            self._connection.execute(
                text(
                    """
                    UPDATE execution_requests
                    SET state='RUNNING'::execution_state,
                        running_at=COALESCE(running_at, CURRENT_TIMESTAMP),
                        started_at=COALESCE(started_at, CURRENT_TIMESTAMP),
                        kubernetes_namespace=:kubernetes_namespace,
                        kubernetes_job_name=:kubernetes_job_name
                    WHERE id=:execution_id
                      AND state='DISPATCHING'::execution_state
                      AND lease_owner=:worker_id
                      AND lease_expires_at > CURRENT_TIMESTAMP
                    RETURNING attempt_count
                    """
                ),
                {
                    "execution_id": execution_id,
                    "worker_id": worker_id,
                    "kubernetes_namespace": kubernetes_namespace,
                    "kubernetes_job_name": kubernetes_job_name,
                },
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            return False
        self._append_event(
            execution_id,
            ExecutionStatus.running,
            {
                "attempt": int(row["attempt_count"]),
                "kubernetes_namespace": kubernetes_namespace,
                "kubernetes_job_name": kubernetes_job_name,
            },
        )
        return True

    def renew_lease(
        self,
        execution_id: UUID,
        *,
        worker_id: str,
        lease_expires_at: datetime,
    ) -> bool:
        validate_lease_deadline(lease_expires_at)
        updated_id = self._connection.execute(
            text(
                """
                UPDATE execution_requests
                SET lease_expires_at=:lease_expires_at
                WHERE id=:execution_id
                  AND lease_owner=:worker_id
                  AND lease_expires_at > CURRENT_TIMESTAMP
                  AND state IN (
                    'DISPATCHING'::execution_state,
                    'RUNNING'::execution_state
                  )
                RETURNING id
                """
            ),
            {
                "execution_id": execution_id,
                "worker_id": worker_id,
                "lease_expires_at": lease_expires_at,
            },
        ).scalar_one_or_none()
        return updated_id is not None

    def expired_leases(self, *, limit: int = 100) -> list[ExpiredExecutionLease]:
        if not 1 <= limit <= 500:
            raise ValueError("limit must be between 1 and 500")
        rows = (
            self._connection.execute(
                text(
                    """
                    SELECT
                        id,
                        state::text AS state,
                        lease_owner,
                        lease_expires_at,
                        kubernetes_namespace,
                        kubernetes_job_name,
                        attempt_count
                    FROM execution_requests
                    WHERE state IN (
                        'DISPATCHING'::execution_state,
                        'RUNNING'::execution_state
                    )
                      AND lease_expires_at < CURRENT_TIMESTAMP
                    ORDER BY lease_expires_at, id
                    FOR UPDATE SKIP LOCKED
                    LIMIT :limit
                    """
                ),
                {"limit": limit},
            )
            .mappings()
            .all()
        )
        return [
            ExpiredExecutionLease(
                execution_id=UUID(str(row["id"])),
                status=ExecutionStatus(str(row["state"])),
                lease_owner=str(row["lease_owner"]) if row["lease_owner"] else None,
                lease_expires_at=row["lease_expires_at"],
                kubernetes_namespace=(
                    str(row["kubernetes_namespace"]) if row["kubernetes_namespace"] else None
                ),
                kubernetes_job_name=(
                    str(row["kubernetes_job_name"]) if row["kubernetes_job_name"] else None
                ),
                attempt_count=int(row["attempt_count"]),
            )
            for row in rows
        ]

    def _append_event(
        self,
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
