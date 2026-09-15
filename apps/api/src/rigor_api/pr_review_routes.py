from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import Connection, text

from .auth import require_permissions
from .database import DatabaseEngine, principal_transaction
from .pr_review_domain import (
    PublicReviewChallenge,
    ReviewCommentInput,
    ReviewGrade,
    ReviewSeverity,
    ReviewVerdict,
    get_public_challenge,
    grade_review,
    review_location_is_valid,
)
from .schemas import AuthenticatedPrincipal

router = APIRouter(prefix="/api/v1/pr-review", tags=["pr-review"])

_CURRENT_USER_SQL = "NULLIF(current_setting('rigor.user_id', true), '')::uuid"


class ReviewRouteModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ReviewSessionCreate(ReviewRouteModel):
    challenge_id: str = Field(min_length=1, max_length=120)


class ReviewSessionView(ReviewRouteModel):
    id: UUID
    challenge_id: str
    status: str
    verdict: ReviewVerdict | None = None
    score: int | None = None
    recall: float | None = None
    precision: float | None = None
    severity_accuracy: float | None = None
    reasoning_quality: float | None = None
    verdict_correct: bool | None = None
    started_at: datetime
    updated_at: datetime
    submitted_at: datetime | None = None


class ReviewCommentCreate(ReviewRouteModel):
    file: str = Field(min_length=1, max_length=500)
    line: int = Field(gt=0)
    severity: ReviewSeverity
    message: str = Field(min_length=1, max_length=4000)

    @field_validator("message")
    @classmethod
    def validate_message(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Review comment cannot be blank")
        return normalized


class ReviewCommentView(ReviewRouteModel):
    id: UUID
    session_id: UUID
    file: str
    line: int
    severity: ReviewSeverity
    message: str
    created_at: datetime


class ReviewSessionDetail(ReviewRouteModel):
    session: ReviewSessionView
    comments: list[ReviewCommentView]


class ReviewSubmitInput(ReviewRouteModel):
    verdict: ReviewVerdict


class ReviewSubmissionView(ReviewRouteModel):
    session: ReviewSessionView
    grade: ReviewGrade


ReviewReadPrincipal = Annotated[
    AuthenticatedPrincipal,
    Depends(require_permissions("profile:read")),
]
ReviewWritePrincipal = Annotated[
    AuthenticatedPrincipal,
    Depends(require_permissions("profile:write")),
]


def _challenge_or_404(challenge_id: str) -> PublicReviewChallenge:
    challenge = get_public_challenge(challenge_id)
    if challenge is None:
        raise HTTPException(
            status_code=404,
            detail="PR review challenge not found",
        )
    return challenge


def _session_select_sql(*, where: str) -> str:
    return f"""
        SELECT
            id,
            challenge_id,
            status,
            verdict,
            score,
            recall,
            precision,
            severity_accuracy,
            reasoning_quality,
            verdict_correct,
            started_at,
            updated_at,
            submitted_at
        FROM pr_review_sessions
        WHERE user_id={_CURRENT_USER_SQL}
          AND {where}
    """


def _session_view(row: Any) -> ReviewSessionView:
    verdict_value = str(row["verdict"]) if row["verdict"] is not None else None
    return ReviewSessionView(
        id=UUID(str(row["id"])),
        challenge_id=str(row["challenge_id"]),
        status=str(row["status"]),
        verdict=ReviewVerdict(verdict_value) if verdict_value else None,
        score=int(row["score"]) if row["score"] is not None else None,
        recall=float(row["recall"]) if row["recall"] is not None else None,
        precision=(
            float(row["precision"])
            if row["precision"] is not None
            else None
        ),
        severity_accuracy=(
            float(row["severity_accuracy"])
            if row["severity_accuracy"] is not None
            else None
        ),
        reasoning_quality=(
            float(row["reasoning_quality"])
            if row["reasoning_quality"] is not None
            else None
        ),
        verdict_correct=(
            bool(row["verdict_correct"])
            if row["verdict_correct"] is not None
            else None
        ),
        started_at=row["started_at"],
        updated_at=row["updated_at"],
        submitted_at=row["submitted_at"],
    )


def _comment_view(row: Any) -> ReviewCommentView:
    return ReviewCommentView(
        id=UUID(str(row["id"])),
        session_id=UUID(str(row["session_id"])),
        file=str(row["file_path"]),
        line=int(row["line_number"]),
        severity=ReviewSeverity(str(row["severity"])),
        message=str(row["message"]),
        created_at=row["created_at"],
    )


def _session_row(connection: Connection, session_id: UUID) -> Any:
    row = connection.execute(
        text(_session_select_sql(where="id=:session_id")),
        {"session_id": session_id},
    ).mappings().one_or_none()
    if row is None:
        raise HTTPException(
            status_code=404,
            detail="PR review session not found",
        )
    return row


def _require_active_session(
    connection: Connection,
    session_id: UUID,
) -> Any:
    row = _session_row(connection, session_id)
    if str(row["status"]) != "active":
        raise HTTPException(
            status_code=409,
            detail="PR review session has already been submitted",
        )
    return row


def _comment_rows(
    connection: Connection,
    session_id: UUID,
) -> list[Any]:
    return list(
        connection.execute(
            text(
                f"""
                SELECT
                    id,
                    session_id,
                    file_path,
                    line_number,
                    severity,
                    message,
                    created_at
                FROM pr_review_comments
                WHERE session_id=:session_id
                  AND user_id={_CURRENT_USER_SQL}
                ORDER BY created_at, id
                """
            ),
            {"session_id": session_id},
        ).mappings().all()
    )


@router.get(
    "/challenges/{challenge_id}",
    response_model=PublicReviewChallenge,
)
def get_review_challenge(
    challenge_id: str,
    _principal: ReviewReadPrincipal,
) -> PublicReviewChallenge:
    return _challenge_or_404(challenge_id)


@router.post(
    "/sessions",
    response_model=ReviewSessionView,
    status_code=201,
)
def create_review_session(
    payload: ReviewSessionCreate,
    principal: ReviewWritePrincipal,
    engine: DatabaseEngine,
) -> ReviewSessionView:
    _challenge_or_404(payload.challenge_id)
    with principal_transaction(engine, principal) as connection:
        row = connection.execute(
            text(
                f"""
                INSERT INTO pr_review_sessions (user_id, challenge_id)
                VALUES ({_CURRENT_USER_SQL}, :challenge_id)
                RETURNING id
                """
            ),
            {"challenge_id": payload.challenge_id},
        ).mappings().one()
        session_id = UUID(str(row["id"]))
        return _session_view(_session_row(connection, session_id))


@router.get(
    "/sessions",
    response_model=list[ReviewSessionView],
)
def list_review_sessions(
    principal: ReviewReadPrincipal,
    engine: DatabaseEngine,
) -> list[ReviewSessionView]:
    with principal_transaction(engine, principal) as connection:
        rows = connection.execute(
            text(
                _session_select_sql(where="TRUE")
                + " ORDER BY updated_at DESC, started_at DESC LIMIT 50"
            )
        ).mappings().all()
        return [_session_view(row) for row in rows]


@router.get(
    "/sessions/{session_id}",
    response_model=ReviewSessionDetail,
)
def get_review_session(
    session_id: UUID,
    principal: ReviewReadPrincipal,
    engine: DatabaseEngine,
) -> ReviewSessionDetail:
    with principal_transaction(engine, principal) as connection:
        session = _session_view(_session_row(connection, session_id))
        comments = [
            _comment_view(row)
            for row in _comment_rows(connection, session_id)
        ]
        return ReviewSessionDetail(
            session=session,
            comments=comments,
        )


@router.post(
    "/sessions/{session_id}/comments",
    response_model=ReviewCommentView,
    status_code=201,
)
def create_review_comment(
    session_id: UUID,
    payload: ReviewCommentCreate,
    principal: ReviewWritePrincipal,
    engine: DatabaseEngine,
) -> ReviewCommentView:
    with principal_transaction(engine, principal) as connection:
        session_row = _require_active_session(connection, session_id)
        challenge_id = str(session_row["challenge_id"])
        if not review_location_is_valid(
            challenge_id,
            payload.file,
            payload.line,
        ):
            raise HTTPException(
                status_code=422,
                detail="Review comment targets an unknown diff line",
            )
        row = connection.execute(
            text(
                f"""
                INSERT INTO pr_review_comments (
                    user_id,
                    session_id,
                    file_path,
                    line_number,
                    severity,
                    message
                )
                VALUES (
                    {_CURRENT_USER_SQL},
                    :session_id,
                    :file_path,
                    :line_number,
                    :severity,
                    :message
                )
                RETURNING
                    id,
                    session_id,
                    file_path,
                    line_number,
                    severity,
                    message,
                    created_at
                """
            ),
            {
                "session_id": session_id,
                "file_path": payload.file,
                "line_number": payload.line,
                "severity": payload.severity.value,
                "message": payload.message,
            },
        ).mappings().one()
        connection.execute(
            text(
                f"""
                UPDATE pr_review_sessions
                SET updated_at=CURRENT_TIMESTAMP
                WHERE id=:session_id
                  AND user_id={_CURRENT_USER_SQL}
                """
            ),
            {"session_id": session_id},
        )
        return _comment_view(row)


@router.delete(
    "/sessions/{session_id}/comments/{comment_id}",
    status_code=204,
)
def delete_review_comment(
    session_id: UUID,
    comment_id: UUID,
    principal: ReviewWritePrincipal,
    engine: DatabaseEngine,
) -> Response:
    with principal_transaction(engine, principal) as connection:
        _require_active_session(connection, session_id)
        deleted = connection.execute(
            text(
                f"""
                DELETE FROM pr_review_comments
                WHERE id=:comment_id
                  AND session_id=:session_id
                  AND user_id={_CURRENT_USER_SQL}
                RETURNING id
                """
            ),
            {
                "comment_id": comment_id,
                "session_id": session_id,
            },
        ).scalar_one_or_none()
        if deleted is None:
            raise HTTPException(
                status_code=404,
                detail="PR review comment not found",
            )
        connection.execute(
            text(
                f"""
                UPDATE pr_review_sessions
                SET updated_at=CURRENT_TIMESTAMP
                WHERE id=:session_id
                  AND user_id={_CURRENT_USER_SQL}
                """
            ),
            {"session_id": session_id},
        )
    return Response(status_code=204)


@router.post(
    "/sessions/{session_id}/submit",
    response_model=ReviewSubmissionView,
)
def submit_review_session(
    session_id: UUID,
    payload: ReviewSubmitInput,
    principal: ReviewWritePrincipal,
    engine: DatabaseEngine,
) -> ReviewSubmissionView:
    with principal_transaction(engine, principal) as connection:
        session_row = _require_active_session(connection, session_id)
        comment_rows = _comment_rows(connection, session_id)
        if not comment_rows:
            raise HTTPException(
                status_code=422,
                detail="Add at least one review comment before submitting",
            )
        comments = [
            ReviewCommentInput(
                file=str(row["file_path"]),
                line=int(row["line_number"]),
                severity=ReviewSeverity(str(row["severity"])),
                message=str(row["message"]),
            )
            for row in comment_rows
        ]
        grade = grade_review(
            str(session_row["challenge_id"]),
            comments,
            payload.verdict,
        )
        connection.execute(
            text(
                f"""
                UPDATE pr_review_sessions
                SET status='submitted',
                    verdict=:verdict,
                    score=:score,
                    recall=:recall,
                    precision=:precision,
                    severity_accuracy=:severity_accuracy,
                    reasoning_quality=:reasoning_quality,
                    verdict_correct=:verdict_correct,
                    updated_at=CURRENT_TIMESTAMP,
                    submitted_at=CURRENT_TIMESTAMP
                WHERE id=:session_id
                  AND user_id={_CURRENT_USER_SQL}
                """
            ),
            {
                "session_id": session_id,
                "verdict": payload.verdict.value,
                "score": grade.score,
                "recall": grade.recall,
                "precision": grade.precision,
                "severity_accuracy": grade.severity_accuracy,
                "reasoning_quality": grade.reasoning_quality,
                "verdict_correct": grade.verdict_correct,
            },
        )
        return ReviewSubmissionView(
            session=_session_view(_session_row(connection, session_id)),
            grade=grade,
        )
