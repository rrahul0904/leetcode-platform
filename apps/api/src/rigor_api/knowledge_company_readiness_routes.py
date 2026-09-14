from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import Connection, text

from .auth import require_permissions
from .database import DatabaseEngine, principal_transaction
from .schemas import AuthenticatedPrincipal

router = APIRouter(prefix="/api/v1/knowledge/me", tags=["knowledge-progress"])


class CompanyReadiness(BaseModel):
    model_config = ConfigDict(extra="forbid")

    company_id: UUID
    slug: str
    name: str
    problem_count: int = Field(ge=0)
    solved_count: int = Field(ge=0)
    in_progress_count: int = Field(ge=0)
    viewed_count: int = Field(ge=0)
    remaining_count: int = Field(ge=0)
    completion_percent: float = Field(ge=0, le=100)
    last_activity_at: str | None


CandidateReadPrincipal = Annotated[
    AuthenticatedPrincipal,
    Depends(require_permissions("submission:read-own")),
]


def _candidate_id(connection: Connection) -> UUID:
    value = connection.execute(
        text("SELECT NULLIF(current_setting('rigor.user_id', true), '')::uuid")
    ).scalar_one()
    if value is None:
        raise HTTPException(status_code=401, detail="Candidate context is unavailable")
    return UUID(str(value))


def _completion_percent(solved: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return round((solved / total) * 100, 1)


@router.get("/company-readiness", response_model=list[CompanyReadiness])
def candidate_company_readiness(
    principal: CandidateReadPrincipal,
    engine: DatabaseEngine,
) -> list[CompanyReadiness]:
    """Roll candidate-owned progress up over source-backed company observations."""

    with principal_transaction(engine, principal) as connection:
        candidate_id = _candidate_id(connection)
        rows = (
            connection.execute(
                text(
                    """
                    WITH company_problem AS (
                      SELECT c.id AS company_id, c.slug, c.name, observation.problem_id
                      FROM knowledge_companies c
                      JOIN knowledge_company_observations observation
                        ON observation.company_id=c.id
                      JOIN knowledge_problems problem
                        ON problem.id=observation.problem_id
                      WHERE problem.deleted_at IS NULL
                        AND problem.publication_status IN ('published', 'metadata_only')
                      GROUP BY c.id, c.slug, c.name, observation.problem_id
                    )
                    SELECT company_problem.company_id,
                           company_problem.slug,
                           company_problem.name,
                           count(*) AS problem_count,
                           count(*) FILTER (
                             WHERE state.status='solved'
                           ) AS solved_count,
                           count(*) FILTER (
                             WHERE state.status IN ('attempted', 'failed')
                           ) AS in_progress_count,
                           count(*) FILTER (
                             WHERE state.status='viewed'
                           ) AS viewed_count,
                           max(state.last_activity_at)::text AS last_activity_at
                    FROM company_problem
                    LEFT JOIN knowledge_candidate_problem_state state
                      ON state.problem_id=company_problem.problem_id
                     AND state.candidate_id=:candidate_id
                    GROUP BY company_problem.company_id,
                             company_problem.slug,
                             company_problem.name
                    ORDER BY solved_count DESC, problem_count DESC,
                             company_problem.name ASC
                    """
                ),
                {"candidate_id": candidate_id},
            )
            .mappings()
            .all()
        )

    summaries: list[CompanyReadiness] = []
    for row in rows:
        total = int(row["problem_count"])
        solved = int(row["solved_count"])
        summaries.append(
            CompanyReadiness(
                company_id=row["company_id"],
                slug=str(row["slug"]),
                name=str(row["name"]),
                problem_count=total,
                solved_count=solved,
                in_progress_count=int(row["in_progress_count"]),
                viewed_count=int(row["viewed_count"]),
                remaining_count=max(total - solved, 0),
                completion_percent=_completion_percent(solved, total),
                last_activity_at=(
                    str(row["last_activity_at"])
                    if row["last_activity_at"] is not None
                    else None
                ),
            )
        )
    return summaries
