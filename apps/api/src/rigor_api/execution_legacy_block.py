from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from fastapi.routing import APIRoute
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
from .schemas import PracticeRunRequest, PracticeSubmitRequest
from .submissions import router as submissions_router

ASYNC_EXECUTION_PATHS = {
    "/api/v1/questions/{slug}/run",
    "/api/v1/questions/{slug}/submissions",
    "/api/v1/executions/{execution_id}",
    "/api/v1/executions/{execution_id}/cancel",
}
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


def _remove_routes(router: APIRouter, paths: set[str]) -> None:
    router.routes[:] = [
        route
        for route in router.routes
        if not (
            isinstance(route, APIRoute)
            and route.path in paths
            and route.methods is not None
            and not route.methods.isdisjoint({"GET", "POST"})
        )
    ]


def _execution_metadata(
    engine: DatabaseEngine,
    principal,
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
    principal,
) -> CanonicalExecutionAccepted:
    metadata = _execution_metadata(engine, principal, accepted.execution_id)
    return CanonicalExecutionAccepted(
        execution_id=accepted.execution_id,
        submission_id=accepted.submission_id,
        execution_type=str(metadata["execution_type"]),
        status=AsyncExecutionStatus(str(metadata["state"])),
        attempt=int(metadata["attempt_count"]),
        created_at=metadata["created_at"],
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
    principal,
) -> CanonicalExecutionView:
    metadata = _execution_metadata(engine, principal, view.execution_id)
    memory_value = metadata["memory_peak_bytes"]
    return CanonicalExecutionView(
        execution_id=view.execution_id,
        submission_id=view.submission_id,
        status=view.status,
        execution_type=view.execution_type,
        runtime=view.runtime,
        attempt=int(metadata["attempt_count"]),
        created_at=view.created_at,
        queued_at=view.queued_at,
        dispatch_started_at=view.dispatch_started_at,
        running_at=view.running_at,
        completed_at=view.completed_at,
        runtime_ms=view.runtime_ms,
        memory_peak_bytes=int(memory_value) if memory_value is not None else None,
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


# The legacy submissions module still contains the old synchronous implementation
# for trusted development/reference compatibility. Remove those HTTP routes before
# FastAPI mounts the router, then register the production asynchronous contract on
# the exact public paths clients already use.
_remove_routes(submissions_router, ASYNC_EXECUTION_PATHS)

submissions_router.add_api_route(
    "/questions/{slug}/run",
    queue_run_for_question,
    methods=["POST"],
    response_model=CanonicalExecutionAccepted,
    status_code=status.HTTP_202_ACCEPTED,
)
submissions_router.add_api_route(
    "/questions/{slug}/submissions",
    queue_submit_for_question,
    methods=["POST"],
    response_model=CanonicalExecutionAccepted,
    status_code=status.HTTP_202_ACCEPTED,
)
submissions_router.add_api_route(
    "/executions/{execution_id}",
    get_candidate_execution,
    methods=["GET"],
    response_model=CanonicalExecutionView,
)
submissions_router.add_api_route(
    "/executions/{execution_id}/cancel",
    cancel_candidate_execution,
    methods=["POST"],
    response_model=CanonicalExecutionView,
)

EXECUTION_ROUTES_REGISTERED = True
LEGACY_SYNCHRONOUS_EXECUTION_BLOCKED = True
