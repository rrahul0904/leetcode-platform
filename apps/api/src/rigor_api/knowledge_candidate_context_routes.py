from __future__ import annotations

from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text

from .auth import require_permissions
from .database import DatabaseEngine, principal_transaction
from .knowledge_progress_routes import _candidate_id, _ensure_state, _state
from .schemas import AuthenticatedPrincipal

router = APIRouter(prefix="/knowledge/me/problem-context", tags=["knowledge-progress"])

CandidateAvailability = Literal["runnable", "published", "reference_only"]

CANDIDATE_PROBLEM_VISIBILITY_SQL = """
p.deleted_at IS NULL
AND (
  p.publication_status='published'
  OR (
    p.publication_status='metadata_only'
    AND length(trim(COALESCE(p.description, ''))) = 0
  )
)
""".strip()

VERIFIED_RUNTIME_SQL = """
EXISTS (
  SELECT 1
  FROM knowledge_problem_runtime_links runtime_link
  JOIN questions runtime_question ON runtime_question.id=runtime_link.question_id
  JOIN question_versions runtime_version
    ON runtime_version.id=runtime_link.question_version_id
  WHERE runtime_link.problem_id=p.id
    AND runtime_link.link_status='verified'
    AND runtime_question.current_published_version_id=runtime_link.question_version_id
    AND runtime_version.state='published'::content_state
)
""".strip()


class CandidateContextModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CandidateActivityRecord(CandidateContextModel):
    id: UUID
    event_type: str
    language: str | None
    duration_seconds: int = Field(ge=0)
    payload: dict[str, object]
    idempotency_key: str | None
    occurred_at: str


class CandidateExecutionRecord(CandidateContextModel):
    execution_id: UUID
    practice_session_id: UUID
    submission_id: UUID | None
    execution_type: str
    runtime: str
    status: str
    created_at: str
    completed_at: str | None
    runtime_ms: int | None
    public_passed: int
    public_total: int
    hidden_passed: int
    hidden_total: int


class CandidateProblemContext(CandidateContextModel):
    problem_id: UUID
    slug: str
    availability: CandidateAvailability
    practice_question_slug: str | None
    practice_runtime: str | None
    state: dict[str, object]
    recent_activity: list[CandidateActivityRecord]
    recent_executions: list[CandidateExecutionRecord]


CandidateReadPrincipal = Annotated[
    AuthenticatedPrincipal,
    Depends(require_permissions("submission:read-own")),
]


def _problem_context_row(connection, slug: str):
    return (
        connection.execute(
            text(
                f"""
                SELECT p.id, p.slug,
                       CASE
                         WHEN p.publication_status='published'
                              AND ({VERIFIED_RUNTIME_SQL}) THEN 'runnable'
                         WHEN p.publication_status='published' THEN 'published'
                         ELSE 'reference_only'
                       END AS availability,
                       (
                         SELECT q.slug
                         FROM knowledge_problem_runtime_links l
                         JOIN questions q ON q.id=l.question_id
                         JOIN question_versions v ON v.id=l.question_version_id
                         WHERE l.problem_id=p.id
                           AND l.link_status='verified'
                           AND q.current_published_version_id=l.question_version_id
                           AND v.state='published'::content_state
                         LIMIT 1
                       ) AS practice_question_slug,
                       (
                         SELECT l.runtime
                         FROM knowledge_problem_runtime_links l
                         JOIN questions q ON q.id=l.question_id
                         JOIN question_versions v ON v.id=l.question_version_id
                         WHERE l.problem_id=p.id
                           AND l.link_status='verified'
                           AND q.current_published_version_id=l.question_version_id
                           AND v.state='published'::content_state
                         LIMIT 1
                       ) AS practice_runtime
                FROM knowledge_problems p
                WHERE p.slug=:slug AND {CANDIDATE_PROBLEM_VISIBILITY_SQL}
                """
            ),
            {"slug": slug},
        )
        .mappings()
        .one_or_none()
    )


def _activity(connection, candidate_id: UUID, problem_id: UUID, limit: int):
    rows = (
        connection.execute(
            text(
                """
                SELECT id, event_type, language, duration_seconds, payload,
                       idempotency_key, occurred_at::text AS occurred_at
                FROM knowledge_activity_events
                WHERE candidate_id=:candidate_id AND problem_id=:problem_id
                ORDER BY occurred_at DESC, id DESC
                LIMIT :limit
                """
            ),
            {"candidate_id": candidate_id, "problem_id": problem_id, "limit": limit},
        )
        .mappings()
        .all()
    )
    return [CandidateActivityRecord.model_validate(dict(row)) for row in rows]


def _executions(connection, candidate_id: UUID, problem_id: UUID, limit: int):
    rows = (
        connection.execute(
            text(
                """
                SELECT er.id AS execution_id,
                       er.practice_session_id,
                       er.submission_id,
                       er.execution_type,
                       er.runtime,
                       er.state::text AS status,
                       er.created_at::text AS created_at,
                       er.completed_at::text AS completed_at,
                       er.runtime_ms,
                       COALESCE((
                         SELECT count(*) FILTER (
                           WHERE COALESCE((entry->>'passed')::boolean, false)
                         )
                         FROM jsonb_array_elements(
                           COALESCE(epr.public_results, '[]'::jsonb)
                         ) entry
                       ), 0) AS public_passed,
                       COALESCE(jsonb_array_length(epr.public_results), 0) AS public_total,
                       COALESCE(epr.hidden_passed, 0) AS hidden_passed,
                       COALESCE(epr.hidden_total, 0) AS hidden_total
                FROM knowledge_problem_runtime_links l
                JOIN practice_sessions ps
                  ON ps.question_version_id=l.question_version_id
                 AND ps.candidate_id=:candidate_id
                JOIN execution_requests er ON er.practice_session_id=ps.id
                LEFT JOIN execution_public_results epr
                  ON epr.execution_request_id=er.id
                WHERE l.problem_id=:problem_id
                  AND l.link_status='verified'
                ORDER BY er.created_at DESC, er.id DESC
                LIMIT :limit
                """
            ),
            {"candidate_id": candidate_id, "problem_id": problem_id, "limit": limit},
        )
        .mappings()
        .all()
    )
    return [CandidateExecutionRecord.model_validate(dict(row)) for row in rows]


@router.get("/{slug}", response_model=CandidateProblemContext)
def candidate_problem_context(
    slug: str,
    principal: CandidateReadPrincipal,
    engine: DatabaseEngine,
    history_limit: Annotated[int, Query(ge=1, le=100)] = 30,
) -> CandidateProblemContext:
    with principal_transaction(engine, principal) as connection:
        candidate_id = _candidate_id(connection)
        row = _problem_context_row(connection, slug)
        if row is None:
            raise HTTPException(status_code=404, detail="Knowledge-bank problem not found")
        problem_id = UUID(str(row["id"]))
        _ensure_state(connection, candidate_id, problem_id)
        state = _state(connection, candidate_id, problem_id)
        return CandidateProblemContext(
            problem_id=problem_id,
            slug=str(row["slug"]),
            availability=str(row["availability"]),
            practice_question_slug=(
                str(row["practice_question_slug"])
                if row["practice_question_slug"] is not None
                else None
            ),
            practice_runtime=(
                str(row["practice_runtime"])
                if row["practice_runtime"] is not None
                else None
            ),
            state=state.model_dump(mode="json"),
            recent_activity=_activity(connection, candidate_id, problem_id, history_limit),
            recent_executions=_executions(connection, candidate_id, problem_id, history_limit),
        )


from .practice import router as application_router  # noqa: E402

application_router.include_router(router)
