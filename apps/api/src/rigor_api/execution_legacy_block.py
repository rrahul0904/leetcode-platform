from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from fastapi.routing import APIRoute

from .execution_api import (
    AsyncExecutionView,
    ExecutionAccepted,
    cancel_execution,
    get_execution,
    queue_run,
    queue_submit,
)
from .practice import router as practice_router
from .submissions import router as submissions_router

ASYNC_EXECUTION_PATHS = {
    "/api/v1/executions/run",
    "/api/v1/executions/submit",
    "/api/v1/executions/{execution_id}",
    "/api/v1/executions/{execution_id}/cancel",
}
LEGACY_EXECUTION_PATHS = {
    "/api/v1/questions/{slug}/run",
    "/api/v1/questions/{slug}/submissions",
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


def legacy_synchronous_run_disabled(slug: str) -> None:
    del slug
    raise HTTPException(
        status_code=status.HTTP_410_GONE,
        detail="Synchronous candidate execution is disabled. Use /api/v1/executions/run.",
    )


def legacy_synchronous_submit_disabled(slug: str) -> None:
    del slug
    raise HTTPException(
        status_code=status.HTTP_410_GONE,
        detail="Synchronous candidate execution is disabled. Use /api/v1/executions/submit.",
    )


# execution_api initially decorates the practice router because it reuses practice
# domain helpers. Move those routes onto the submissions/execution surface before
# main mounts either router. More importantly, remove the old synchronous
# submissions handlers entirely so no HTTP request can reach
# LocalFunctionalPythonRunner in FastAPI.
_remove_routes(practice_router, ASYNC_EXECUTION_PATHS)
_remove_routes(submissions_router, LEGACY_EXECUTION_PATHS | ASYNC_EXECUTION_PATHS)

submissions_router.add_api_route(
    "/executions/run",
    queue_run,
    methods=["POST"],
    response_model=ExecutionAccepted,
    status_code=status.HTTP_202_ACCEPTED,
)
submissions_router.add_api_route(
    "/executions/submit",
    queue_submit,
    methods=["POST"],
    response_model=ExecutionAccepted,
    status_code=status.HTTP_202_ACCEPTED,
)
submissions_router.add_api_route(
    "/executions/{execution_id}",
    get_execution,
    methods=["GET"],
    response_model=AsyncExecutionView,
)
submissions_router.add_api_route(
    "/executions/{execution_id}/cancel",
    cancel_execution,
    methods=["POST"],
    response_model=AsyncExecutionView,
)
submissions_router.add_api_route(
    "/questions/{slug}/run",
    legacy_synchronous_run_disabled,
    methods=["POST"],
    include_in_schema=False,
)
submissions_router.add_api_route(
    "/questions/{slug}/submissions",
    legacy_synchronous_submit_disabled,
    methods=["POST"],
    include_in_schema=False,
)

LEGACY_SYNCHRONOUS_EXECUTION_BLOCKED = True
