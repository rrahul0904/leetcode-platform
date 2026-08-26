"""Explicit FastAPI serving composition for Rigor.

The package initializer is intentionally side-effect free so CLI/library imports do
not boot FastAPI or evaluate production-only settings.  The historical API module
is retained as ``legacy_main`` while the serving entrypoint removes its synchronous
candidate-code routes and installs the durable execution and governed solution
routers explicitly.
"""

from __future__ import annotations

from fastapi.routing import APIRoute

# These compatibility hooks are serving/runtime concerns.  Import them here rather
# than from rigor_api.__init__ so ordinary library imports remain side-effect free.
from . import attachment_progress_patch as attachment_progress_patch
from . import execution_patches as execution_patches
from .attachment_solution_routes import router as attachment_solution_router
from .execution_routes import router as execution_router
from .legacy_main import *  # noqa: F403
from .legacy_main import app as app

_LEGACY_SYNCHRONOUS_ENDPOINTS = {
    ("/api/v1/questions/{slug}/run", "run_question"),
    ("/api/v1/questions/{slug}/submissions", "submit_question"),
}


def _is_legacy_synchronous_candidate_execution(route: object) -> bool:
    """Identify the in-process execution endpoints that must never be served.

    ``legacy_main`` is kept byte-for-byte for compatibility while this entrypoint
    deliberately removes only its two candidate-code execution routes.  All other
    historical API routes remain unchanged.
    """

    if not isinstance(route, APIRoute):
        return False
    endpoint_name = getattr(route.endpoint, "__name__", "")
    return (route.path, endpoint_name) in _LEGACY_SYNCHRONOUS_ENDPOINTS


app.router.routes[:] = [
    route
    for route in app.router.routes
    if not _is_legacy_synchronous_candidate_execution(route)
]

# Durable Run/Submit must be part of the final serving application before any
# future compatibility router can claim the same public paths.
app.include_router(execution_router)
app.include_router(attachment_solution_router)
