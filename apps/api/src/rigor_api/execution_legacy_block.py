from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, status
from fastapi.routing import APIRoute

from .database import DatabaseEngine
from .execution_api import (
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


def queue_run_for_question(
    slug: str,
    request: PracticeRunRequest,
    principal: CandidateWritePrincipal,
    engine: DatabaseEngine,
    idempotency_key: IdempotencyHeader,
) -> ExecutionAccepted:
    """Create a durable RUN without executing candidate source in FastAPI."""

    return queue_run(request, principal, engine, idempotency_key, slug)


def queue_submit_for_question(
    slug: str,
    request: PracticeSubmitRequest,
    principal: CandidateWritePrincipal,
    engine: DatabaseEngine,
    idempotency_key: IdempotencyHeader,
) -> ExecutionAccepted:
    """Create a durable SUBMIT backed by the same execution service as Run."""

    return queue_submit(request, principal, engine, idempotency_key, slug)


def get_candidate_execution(
    execution_id: UUID,
    principal: CandidateReadPrincipal,
    engine: DatabaseEngine,
) -> AsyncExecutionView:
    return get_execution(execution_id, principal, engine)


def cancel_candidate_execution(
    execution_id: UUID,
    principal: CandidateWritePrincipal,
    engine: DatabaseEngine,
) -> AsyncExecutionView:
    return cancel_execution(execution_id, principal, engine)


# The legacy submissions module still contains the old synchronous implementation
# for trusted development/reference compatibility. Remove those HTTP routes before
# FastAPI mounts the router, then register the production asynchronous contract on
# the exact public paths clients already use.
_remove_routes(submissions_router, ASYNC_EXECUTION_PATHS)

submissions_router.add_api_route(
    "/questions/{slug}/run",
    queue_run_for_question,
    methods=["POST"],
    response_model=ExecutionAccepted,
    status_code=status.HTTP_202_ACCEPTED,
)
submissions_router.add_api_route(
    "/questions/{slug}/submissions",
    queue_submit_for_question,
    methods=["POST"],
    response_model=ExecutionAccepted,
    status_code=status.HTTP_202_ACCEPTED,
)
submissions_router.add_api_route(
    "/executions/{execution_id}",
    get_candidate_execution,
    methods=["GET"],
    response_model=AsyncExecutionView,
)
submissions_router.add_api_route(
    "/executions/{execution_id}/cancel",
    cancel_candidate_execution,
    methods=["POST"],
    response_model=AsyncExecutionView,
)

EXECUTION_ROUTES_REGISTERED = True
LEGACY_SYNCHRONOUS_EXECUTION_BLOCKED = True
