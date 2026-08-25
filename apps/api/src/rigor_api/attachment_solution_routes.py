from __future__ import annotations

from typing import Annotated, Any, cast

from fastapi import Depends, HTTPException
from sqlalchemy import text

from .auth import require_permissions
from .database import DatabaseEngine, principal_transaction
from .practice import candidate_id, router
from .schemas import AuthenticatedPrincipal

CandidateReadPrincipal = Annotated[
    AuthenticatedPrincipal,
    Depends(require_permissions("submission:read-own")),
]


@router.get("/questions/{slug}/solution", tags=["practice"])
def reveal_question_solution(
    slug: str,
    principal: CandidateReadPrincipal,
    engine: DatabaseEngine,
) -> dict[str, Any]:
    """Reveal a source-backed solution without ever returning hidden tests.

    Runnable questions unlock after the candidate completes a submission or
    practice session. Non-runnable study/scenario questions are revealable on
    demand because there is no executable attempt lifecycle to complete.
    """
    with principal_transaction(engine, principal) as connection:
        row = (
            connection.execute(
                text(
                    """
                    SELECT q.id AS question_id, q.slug, v.id AS question_version_id,
                           v.title, v.structured_content, s.reference_solution,
                           s.explanation, s.trade_off_analysis
                    FROM questions q
                    JOIN question_versions v ON v.id=q.current_published_version_id
                    JOIN solutions s ON s.question_version_id=v.id
                    WHERE q.slug=:slug AND q.archived_at IS NULL
                      AND v.state='published'::content_state
                    """
                ),
                {"slug": slug},
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            raise HTTPException(status_code=404, detail="Published solution not found")
        raw_structured = row["structured_content"]
        structured = (
            cast(dict[str, Any], raw_structured)
            if isinstance(raw_structured, dict)
            else {}
        )
        runnable = bool(structured.get("runnable"))
        unlocked = not runnable
        if runnable:
            user_id = candidate_id(connection)
            unlocked = bool(
                connection.execute(
                    text(
                        """
                        SELECT
                          EXISTS (
                            SELECT 1 FROM submissions s
                            WHERE s.candidate_id=:candidate_id
                              AND s.question_version_id=:question_version_id
                              AND s.completed_at IS NOT NULL
                          ) OR EXISTS (
                            SELECT 1 FROM practice_sessions ps
                            WHERE ps.candidate_id=:candidate_id
                              AND ps.question_version_id=:question_version_id
                              AND ps.completed_at IS NOT NULL
                          )
                        """
                    ),
                    {
                        "candidate_id": user_id,
                        "question_version_id": row["question_version_id"],
                    },
                ).scalar_one()
            )
        if not unlocked:
            raise HTTPException(
                status_code=409,
                detail="Complete an attempt before revealing the reference solution.",
            )
        return {
            "question_slug": row["slug"],
            "title": row["title"],
            "reference_solution": row["reference_solution"],
            "explanation": row["explanation"],
            "trade_off_analysis": row["trade_off_analysis"],
            "time_complexity": structured.get("time_complexity"),
            "space_complexity": structured.get("space_complexity"),
            "common_mistakes": structured.get("common_mistakes"),
            "expected_approach": structured.get("expected_approach"),
            "best_practices": structured.get("best_practices"),
            "hidden_tests_revealed": False,
        }
