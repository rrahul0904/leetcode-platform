from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import text

from .config import get_settings
from .database import DatabaseEngine, principal_transaction
from .schemas import AuthenticatedPrincipal
from .vercel_sandbox_execution import VercelSandboxClient, VercelSandboxError

VERCEL_SANDBOX = "VERCEL_SANDBOX"
KUBERNETES_JOB = "KUBERNETES_JOB"


def require_candidate_execution_plane() -> str:
    """Validate the configured execution plane before accepting candidate work.

    Hosted deployments fail closed. In particular, a Vercel deployment must have
    project-scoped Sandbox credentials available before a durable execution row is
    created; otherwise a request could remain queued forever with no worker able to
    claim it.
    """

    settings = get_settings()
    adapter = settings.execution_adapter.strip().upper()
    hosted = settings.environment.strip().lower() in {"production", "staging"}

    if hosted and adapter == VERCEL_SANDBOX:
        try:
            VercelSandboxClient.discover()
        except VercelSandboxError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Candidate execution is temporarily unavailable.",
            ) from exc

    return adapter


def record_execution_adapter(
    engine: DatabaseEngine,
    principal: AuthenticatedPrincipal,
    execution_id: UUID,
    adapter: str,
) -> None:
    """Persist the execution plane selected by the public API for auditability."""

    with principal_transaction(engine, principal) as connection:
        updated = connection.execute(
            text(
                """
                UPDATE execution_requests
                SET adapter=:adapter
                WHERE id=:execution_id
                  AND candidate_id=NULLIF(
                    current_setting('rigor.user_id', true), ''
                  )::uuid
                RETURNING id
                """
            ),
            {"execution_id": execution_id, "adapter": adapter},
        ).scalar_one_or_none()
    if updated is None:
        raise RuntimeError("Queued execution disappeared before adapter assignment.")
