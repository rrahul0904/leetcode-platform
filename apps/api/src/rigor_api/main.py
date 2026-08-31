"""Explicit FastAPI serving composition for SkillsForge AI.

The package initializer is intentionally side-effect free so CLI/library imports do
not boot FastAPI or evaluate production-only settings. The historical API module
is retained as ``legacy_main`` while this serving entrypoint removes candidate-code
execution and candidate-owned read routes from the legacy submissions router *before*
it is included in the app, then installs the durable execution, ownership-hardened
candidate reads, governed solution, and SaaS routers explicitly.
"""

from __future__ import annotations

from fastapi.routing import APIRoute

from . import attachment_progress_patch as attachment_progress_patch
from . import execution_patches as execution_patches
from . import submissions as legacy_submissions
from .attachment_solution_routes import router as attachment_solution_router
from .auth import authenticated_principal, token_validator
from .bookmarked_catalog import router as bookmarked_catalog_router
from .candidate_submission_routes import router as candidate_submission_router
from .career_resume_routes import router as career_resume_router
from .careeros import router as career_os_router
from .execution_capability import router as execution_capability_router
from .execution_routes import router as execution_router
from .principal_auth import database_authoritative_principal
from .question_engagement import router as question_engagement_router
from .saas_routes import router as saas_router
from .session_token_auth import session_token_validator

_LEGACY_REPLACED_ENDPOINTS = {
    ("/api/v1/questions/{slug}/run", "run_question"),
    ("/api/v1/questions/{slug}/submissions", "submit_question"),
    ("/api/v1/submissions", "list_submissions"),
    ("/api/v1/submissions/{submission_id}", "get_submission"),
    ("/api/v1/practice-sessions/{session_id}/submissions", "list_session_submissions"),
    ("/api/v1/me/evidence", "candidate_evidence"),
}


def _is_replaced_legacy_candidate_route(route: object) -> bool:
    if not isinstance(route, APIRoute):
        return False
    endpoint_name = getattr(route.endpoint, "__name__", "")
    return (route.path, endpoint_name) in _LEGACY_REPLACED_ENDPOINTS


legacy_submissions.router.routes[:] = [
    route
    for route in legacy_submissions.router.routes
    if not _is_replaced_legacy_candidate_route(route)
]

from .legacy_main import *  # noqa: E402,F403
from .legacy_main import app as app  # noqa: E402

app.title = "SkillsForge AI API"
app.description = (
    "Production API for SkillsForge AI technical learning, interview preparation, "
    "CareerOS job-fit intelligence, durable execution, identity, and candidate progress."
)

# Resolve the lifespan-created base validator at request time. Local OIDC keeps the
# original validator; external Clerk sessions use the standard session-token-aware
# wrapper and do not require a custom JWT template.
app.dependency_overrides[token_validator] = session_token_validator

# External identity proves who the user is. SkillsForge PostgreSQL remains the
# authority for account status, roles, permissions, and organization membership.
app.dependency_overrides[authenticated_principal] = database_authoritative_principal
app.include_router(execution_capability_router)
app.include_router(execution_router)
app.include_router(candidate_submission_router)
app.include_router(question_engagement_router)
app.include_router(bookmarked_catalog_router)
app.include_router(attachment_solution_router)
app.include_router(career_resume_router)
app.include_router(career_os_router)
app.include_router(saas_router)