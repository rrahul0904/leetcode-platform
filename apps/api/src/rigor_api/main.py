"""Explicit FastAPI serving composition for SkillForge AI.

The package initializer is intentionally side-effect free so CLI/library imports do
not boot FastAPI or evaluate production-only settings. The historical API module
is retained as ``legacy_main`` while this serving entrypoint removes candidate-code
execution from the legacy submissions router *before* it is included in the app,
then installs the durable execution, governed solution, and SaaS routers explicitly.
"""

from __future__ import annotations

from fastapi.routing import APIRoute

from . import attachment_progress_patch as attachment_progress_patch
from . import execution_patches as execution_patches
from . import submissions as legacy_submissions
from .attachment_solution_routes import router as attachment_solution_router
from .execution_routes import router as execution_router
from .saas_routes import router as saas_router

_LEGACY_SYNCHRONOUS_ENDPOINTS = {
    ("/api/v1/questions/{slug}/run", "run_question"),
    ("/api/v1/questions/{slug}/submissions", "submit_question"),
}


def _is_legacy_synchronous_candidate_execution(route: object) -> bool:
    if not isinstance(route, APIRoute):
        return False
    endpoint_name = getattr(route.endpoint, "__name__", "")
    return (route.path, endpoint_name) in _LEGACY_SYNCHRONOUS_ENDPOINTS


legacy_submissions.router.routes[:] = [
    route
    for route in legacy_submissions.router.routes
    if not _is_legacy_synchronous_candidate_execution(route)
]

from .legacy_main import *  # noqa: E402,F403
from .legacy_main import app as app  # noqa: E402

app.title = "SkillForge AI API"
app.description = (
    "Production API for SkillForge AI technical learning, interview preparation, "
    "durable execution, identity, and candidate progress."
)
app.include_router(execution_router)
app.include_router(attachment_solution_router)
app.include_router(saas_router)
