from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException
from sqlalchemy import Connection, text

from .database import DatabaseEngine, principal_transaction
from .practice import PracticeSessionNotFoundError, PracticeSessionRepository
from .schemas import CandidateEvidence, CandidateSubmission
from .submissions import CandidateReadPrincipal, _submission

router = APIRouter(prefix="/api/v1", tags=["candidate-submissions"])


def _owned_submission_id(connection: Connection, submission_id: UUID) -> UUID:
    value = connection.execute(
        text(
            """
            SELECT id
            FROM submissions
            WHERE id=:submission_id
              AND candidate_id=NULLIF(
                current_setting('rigor.user_id', true), ''
              )::uuid
            """
        ),
        {"submission_id": submission_id},
    ).scalar_one_or_none()
    if value is None:
        raise HTTPException(status_code=404, detail="Submission not found.")
    return UUID(str(value))


@router.get("/submissions", response_model=list[CandidateSubmission])
def list_candidate_submissions(
    principal: CandidateReadPrincipal,
    engine: DatabaseEngine,
) -> list[CandidateSubmission]:
    with principal_transaction(engine, principal) as connection:
        ids = connection.execute(
            text(
                """
                SELECT id
                FROM submissions
                WHERE candidate_id=NULLIF(
                    current_setting('rigor.user_id', true), ''
                )::uuid
                ORDER BY created_at DESC
                LIMIT 100
                """
            )
        ).scalars()
        return [_submission(connection, UUID(str(value))) for value in ids]


@router.get("/submissions/{submission_id}", response_model=CandidateSubmission)
def get_candidate_submission(
    submission_id: UUID,
    principal: CandidateReadPrincipal,
    engine: DatabaseEngine,
) -> CandidateSubmission:
    with principal_transaction(engine, principal) as connection:
        owned_id = _owned_submission_id(connection, submission_id)
        return _submission(connection, owned_id)


@router.get(
    "/practice-sessions/{session_id}/submissions",
    response_model=list[CandidateSubmission],
)
def list_candidate_session_submissions(
    session_id: UUID,
    principal: CandidateReadPrincipal,
    engine: DatabaseEngine,
) -> list[CandidateSubmission]:
    with principal_transaction(engine, principal) as connection:
        try:
            PracticeSessionRepository(connection).get(session_id)
        except PracticeSessionNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Practice session not found.") from exc
        ids = connection.execute(
            text(
                """
                SELECT id
                FROM submissions
                WHERE practice_session_id=:session_id
                  AND candidate_id=NULLIF(
                    current_setting('rigor.user_id', true), ''
                  )::uuid
                ORDER BY created_at DESC
                """
            ),
            {"session_id": session_id},
        ).scalars()
        return [_submission(connection, UUID(str(value))) for value in ids]


@router.get("/me/evidence", response_model=list[CandidateEvidence])
def candidate_owned_evidence(
    principal: CandidateReadPrincipal,
    engine: DatabaseEngine,
) -> list[CandidateEvidence]:
    with principal_transaction(engine, principal) as connection:
        rows = (
            connection.execute(
                text(
                    """
                    SELECT e.id, e.competency_id, c.slug AS competency_slug,
                           c.name AS competency_name, e.source_type, e.source_id,
                           e.score, e.confidence, e.weight,
                           e.evaluator_version, e.evidence AS metadata,
                           e.observed_at
                    FROM candidate_competency_evidence e
                    JOIN competencies c ON c.id=e.competency_id
                    WHERE e.candidate_id=NULLIF(
                        current_setting('rigor.user_id', true), ''
                    )::uuid
                    ORDER BY e.observed_at DESC
                    """
                )
            )
            .mappings()
            .all()
        )
        return [CandidateEvidence.model_validate(dict(row)) for row in rows]
