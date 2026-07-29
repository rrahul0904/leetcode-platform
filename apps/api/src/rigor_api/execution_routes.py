from __future__ import annotations

from datetime import datetime
from typing import cast
from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text

from .database import DatabaseEngine, principal_transaction
from .execution_api import (
    AsyncExecutionResult,
    AsyncExecutionStatus,
    AsyncExecutionView,
    CandidateReadPrincipal,
    CandidateWritePrincipal,
    ExecutionAccepted,
    IdempotencyHeader,
    cancel_execution,
    get_execution,
    queue_run,
    queue_submit,
)
from .practice import router as practice_router
from .schemas import AuthenticatedPrincipal, PracticeRunRequest, PracticeSubmitRequest

router = APIRouter(tags=["execution"])
TERMINAL_STATUSES = {
    AsyncExecutionStatus.completed,
    AsyncExecutionStatus.failed,
    AsyncExecutionStatus.timeout,
    AsyncExecutionStatus.cancelled,
}
INFRASTRUCTURE_ERROR_CATEGORIES = {
    "execution_attempt_limit",
    "runner_result_unavailable",
    "sandbox_missing",
    "sandbox_missing_after_lease_expiry",
    "trusted_result_validation_failed",
    "unsupported_execution_language",
}


class PublicExecutionModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CanonicalExecutionAccepted(PublicExecutionModel):
    execution_id: UUID
    submission_id: UUID | None
    execution_type: str
    status: AsyncExecutionStatus
    attempt: int = Field(ge=0)
    created_at: datetime
    status_url: str
    duplicate: bool = False


class CanonicalExecutionView(PublicExecutionModel):
    execution_id: UUID
    submission_id: UUID | None
    status: AsyncExecutionStatus
    execution_type: str
    runtime: str
    attempt: int = Field(ge=0)
    created_at: datetime
    queued_at: datetime
    dispatch_started_at: datetime | None
    running_at: datetime | None
    completed_at: datetime | None
    runtime_ms: int | None = Field(default=None, ge=0)
    memory_peak_bytes: int | None = Field(default=None, ge=0)
    result: AsyncExecutionResult | None = None
    error: str | None = None


def _integer(value: object, *, field: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise RuntimeError(f"Execution metadata field {field!r} is invalid.")
    return value


def _execution_metadata(
    engine: DatabaseEngine,
    principal: AuthenticatedPrincipal,
    execution_id: UUID,
) -> dict[str, object]:
    with principal_transaction(engine, principal) as connection:
        row = (
            connection.execute(
                text(
                    """
                    SELECT execution_type, state::text AS state, attempt_count,
                           created_at, memory_peak_bytes
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
        raise HTTPException(status_code=404, detail="Execution not found.")
    return dict(row)


def _accepted_contract(
    accepted: ExecutionAccepted,
    *,
    engine: DatabaseEngine,
    principal: AuthenticatedPrincipal,
) -> CanonicalExecutionAccepted:
    metadata = _execution_metadata(engine, principal, accepted.execution_id)
    return CanonicalExecutionAccepted(
        execution_id=accepted.execution_id,
        submission_id=accepted.submission_id,
        execution_type=str(metadata["execution_type"]),
        status=AsyncExecutionStatus(str(metadata["state"])),
        attempt=_integer(metadata["attempt_count"], field="attempt_count"),
        created_at=cast(datetime, metadata["created_at"]),
        status_url=f"/api/v1/executions/{accepted.execution_id}",
        duplicate=accepted.duplicate,
    )


def _safe_error(view: AsyncExecutionView) -> str | None:
    if view.status is AsyncExecutionStatus.timeout:
        return "TIMEOUT"
    if view.status is AsyncExecutionStatus.cancelled:
        return "CANCELLED"
    if view.status is not AsyncExecutionStatus.failed:
        return None
    if view.error_category in INFRASTRUCTURE_ERROR_CATEGORIES:
        return "INFRASTRUCTURE_ERROR"
    return "CANDIDATE_EXECUTION_ERROR"


def _view_contract(
    view: AsyncExecutionView,
    *,
    engine: DatabaseEngine,
    principal: AuthenticatedPrincipal,
) -> CanonicalExecutionView:
    metadata = _execution_metadata(engine, principal, view.execution_id)
    memory_value = metadata["memory_peak_bytes"]
    if memory_value is not None and (
        not isinstance(memory_value, int) or isinstance(memory_value, bool)
    ):
        raise RuntimeError("Execution memory metadata is invalid.")
    return CanonicalExecutionView(
        execution_id=view.execution_id,
        submission_id=view.submission_id,
        status=view.status,
        execution_type=view.execution_type,
        runtime=view.runtime,
        attempt=_integer(metadata["attempt_count"], field="attempt_count"),
        created_at=view.created_at,
        queued_at=view.queued_at,
        dispatch_started_at=view.dispatch_started_at,
        running_at=view.running_at,
        completed_at=view.completed_at,
        runtime_ms=view.runtime_ms,
        memory_peak_bytes=memory_value,
        result=view.result,
        error=_safe_error(view),
    )


def queue_run_for_question(
    slug: str,
    request: PracticeRunRequest,
    principal: CandidateWritePrincipal,
    engine: DatabaseEngine,
    idempotency_key: IdempotencyHeader,
) -> CanonicalExecutionAccepted:
    """Create a durable RUN without executing candidate source in FastAPI."""

    accepted = queue_run(request, principal, engine, idempotency_key, slug)
    return _accepted_contract(accepted, engine=engine, principal=principal)


def queue_submit_for_question(
    slug: str,
    request: PracticeSubmitRequest,
    principal: CandidateWritePrincipal,
    engine: DatabaseEngine,
    idempotency_key: IdempotencyHeader,
) -> CanonicalExecutionAccepted:
    """Create a durable SUBMIT backed by the same execution service as Run."""

    accepted = queue_submit(request, principal, engine, idempotency_key, slug)
    return _accepted_contract(accepted, engine=engine, principal=principal)


def get_candidate_execution(
    execution_id: UUID,
    principal: CandidateReadPrincipal,
    engine: DatabaseEngine,
) -> CanonicalExecutionView:
    view = get_execution(execution_id, principal, engine)
    return _view_contract(view, engine=engine, principal=principal)


def cancel_candidate_execution(
    execution_id: UUID,
    principal: CandidateWritePrincipal,
    engine: DatabaseEngine,
) -> CanonicalExecutionView:
    current = get_execution(execution_id, principal, engine)
    if current.status in TERMINAL_STATUSES:
        return _view_contract(current, engine=engine, principal=principal)
    try:
        cancelled = cancel_execution(execution_id, principal, engine)
    except HTTPException as exc:
        if exc.status_code != 409:
            raise
        # Completion may win the cancellation race after the first read. Treat
        # the now-terminal aggregate as an idempotent cancellation response.
        raced = get_execution(execution_id, principal, engine)
        if raced.status not in TERMINAL_STATUSES:
            raise
        cancelled = raced
    return _view_contract(cancelled, engine=engine, principal=principal)


router.add_api_route(
    "/questions/{slug}/run",
    queue_run_for_question,
    methods=["POST"],
    response_model=CanonicalExecutionAccepted,
    status_code=status.HTTP_202_ACCEPTED,
)
router.add_api_route(
    "/questions/{slug}/submissions",
    queue_submit_for_question,
    methods=["POST"],
    response_model=CanonicalExecutionAccepted,
    status_code=status.HTTP_202_ACCEPTED,
)
router.add_api_route(
    "/executions/{execution_id}",
    get_candidate_execution,
    methods=["GET"],
    response_model=CanonicalExecutionView,
)
router.add_api_route(
    "/executions/{execution_id}/cancel",
    cancel_candidate_execution,
    methods=["POST"],
    response_model=CanonicalExecutionView,
)

# APIRouter.include_router does not inherit the containing router's prefix.
# Apply the public API prefix explicitly before main.py mounts practice_router.
practice_router.include_router(router, prefix="/api/v1")

EXECUTION_ROUTES_REGISTERED = True
LEGACY_SYNCHRONOUS_EXECUTION_BLOCKED = True
