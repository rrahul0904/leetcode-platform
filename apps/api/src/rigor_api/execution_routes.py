from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from .execution_api import (
    AsyncExecutionView,
    ExecutionAccepted,
    cancel_execution,
    get_execution,
    queue_run,
    queue_submit,
)
from .practice import router as practice_router

router = APIRouter(tags=["execution"])

router.add_api_route(
    "/executions/run",
    queue_run,
    methods=["POST"],
    response_model=ExecutionAccepted,
    status_code=status.HTTP_202_ACCEPTED,
)
router.add_api_route(
    "/executions/submit",
    queue_submit,
    methods=["POST"],
    response_model=ExecutionAccepted,
    status_code=status.HTTP_202_ACCEPTED,
)
router.add_api_route(
    "/executions/{execution_id}",
    get_execution,
    methods=["GET"],
    response_model=AsyncExecutionView,
)
router.add_api_route(
    "/executions/{execution_id}/cancel",
    cancel_execution,
    methods=["POST"],
    response_model=AsyncExecutionView,
)


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


router.add_api_route(
    "/questions/{slug}/run",
    legacy_synchronous_run_disabled,
    methods=["POST"],
    include_in_schema=False,
)
router.add_api_route(
    "/questions/{slug}/submissions",
    legacy_synchronous_submit_disabled,
    methods=["POST"],
    include_in_schema=False,
)

# main.py already mounts practice_router before the legacy submissions router.
# Attaching this dedicated router here makes async execution explicit and gives
# the fail-closed compatibility handlers route priority without rewriting the
# existing submissions domain in this production-safety phase.
practice_router.include_router(router)

EXECUTION_ROUTES_REGISTERED = True
LEGACY_SYNCHRONOUS_EXECUTION_BLOCKED = True
