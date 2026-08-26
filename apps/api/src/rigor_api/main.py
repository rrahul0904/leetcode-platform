"""Explicit FastAPI serving composition for Rigor.

The package initializer is intentionally side-effect free so CLI/library imports do
not boot FastAPI or evaluate production-only settings. The historical API module
is retained as ``legacy_main`` while this serving entrypoint removes candidate-code
execution from the legacy submissions router *before* it is included in the app,
then installs the durable execution and governed solution routers explicitly.
"""

from __future__ import annotations

from fastapi.routing import APIRoute

# These compatibility hooks are serving/runtime concerns. Import them here rather
# than from rigor_api.__init__ so ordinary library imports remain side-effect free.
from . import attachment_progress_patch as attachment_progress_patch
from . import execution_patches as execution_patches
from . import submissions as legacy_submissions
from .attachment_solution_routes import router as attachment_solution_router
from .execution_routes import router as execution_router

_LEGACY_SYNCHRONOUS_ENDPOINTS = {
    ("/api/v1/questions/{slug}/run", "run_question"),
    ("/api/v1/questions/{slug}/submissions", "submit_question"),
}


def _is_legacy_synchronous_candidate_execution(route: object) -> bool:
    """Identify in-process candidate execution routes that must never be served."""

    if not isinstance(route, APIRoute):
        return False
    endpoint_name = getattr(route.endpoint, "__name__", "")
    return (route.path, endpoint_name) in _LEGACY_SYNCHRONOUS_ENDPOINTS


# FastAPI preserves included routers as nested route groups in current releases.
# Removing these handlers after app.include_router() is therefore too late: the
# nested submissions router can still win route selection. Prune the source router
# before legacy_main composes the application so there is no candidate-facing path
# capable of invoking LocalFunctionalPythonRunner inside FastAPI.
legacy_submissions.router.routes[:] = [
    route
    for route in legacy_submissions.router.routes
    if not _is_legacy_synchronous_candidate_execution(route)
]

from .legacy_main import *  # noqa: E402,F403
from .legacy_main import app as app  # noqa: E402

# Durable Run/Submit and governed solution reveal are the sole serving routes for
# these public contracts.
app.include_router(execution_router)
app.include_router(attachment_solution_router)
