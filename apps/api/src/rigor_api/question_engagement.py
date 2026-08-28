from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import Connection, text

from .auth import require_permissions
from .database import DatabaseEngine, principal_transaction
from .schemas import AuthenticatedPrincipal

router = APIRouter(prefix="/api/v1", tags=["candidate-engagement"])


class EngagementModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class QuestionNoteInput(EngagementModel):
    body: str = Field(min_length=1, max_length=10_000)


class QuestionNoteView(EngagementModel):
    id: UUID
    question_slug: str
    body: str
    created_at: datetime
    updated_at: datetime


class QuestionEngagementView(EngagementModel):
    question_slug: str
    bookmarked: bool
    notes: list[QuestionNoteView]


class BookmarkItem(EngagementModel):
    question_slug: str
    title: str
    created_at: datetime


CandidateEngagementReadPrincipal = Annotated[
    AuthenticatedPrincipal,
    Depends(require_permissions("profile:read")),
]
CandidateEngagementWritePrincipal = Annotated[
    AuthenticatedPrincipal,
    Depends(require_permissions("profile:write")),
]


def _question_id(connection: Connection, slug: str) -> UUID:
    value = connection.execute(
        text(
            """
            SELECT q.id
            FROM questions q
            JOIN question_versions v ON v.id=q.current_published_version_id
            WHERE q.slug=:slug
              AND q.archived_at IS NULL
              AND v.state='published'::content_state
            """
        ),
        {"slug": slug},
    ).scalar_one_or_none()
    if value is None:
        raise HTTPException(status_code=404, detail="Published question not found")
    return UUID(str(value))


def _notes(connection: Connection, *, question_id: UUID, slug: str) -> list[QuestionNoteView]:
    rows = connection.execute(
        text(
            """
            SELECT id, body, created_at, updated_at
            FROM candidate_question_notes
            WHERE question_id=:question_id
            ORDER BY updated_at DESC, created_at DESC
            """
        ),
        {"question_id": question_id},
    ).mappings().all()
    return [
        QuestionNoteView(
            id=UUID(str(row["id"])),
            question_slug=slug,
            body=str(row["body"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
        for row in rows
    ]


def get_question_engagement(
    slug: str,
    principal: CandidateEngagementReadPrincipal,
    engine: DatabaseEngine,
) -> QuestionEngagementView:
    with principal_transaction(engine, principal) as connection:
        question_id = _question_id(connection, slug)
        bookmarked = connection.execute(
            text(
                """
                SELECT EXISTS(
                    SELECT 1
                    FROM candidate_question_bookmarks
                    WHERE question_id=:question_id
                )
                """
            ),
            {"question_id": question_id},
        ).scalar_one()
        return QuestionEngagementView(
            question_slug=slug,
            bookmarked=bool(bookmarked),
            notes=_notes(connection, question_id=question_id, slug=slug),
        )


def list_candidate_bookmarks(
    principal: CandidateEngagementReadPrincipal,
    engine: DatabaseEngine,
) -> list[BookmarkItem]:
    with principal_transaction(engine, principal) as connection:
        rows = connection.execute(
            text(
                """
                SELECT q.slug AS question_slug, v.title, b.created_at
                FROM candidate_question_bookmarks b
                JOIN questions q ON q.id=b.question_id
                JOIN question_versions v ON v.id=q.current_published_version_id
                WHERE q.archived_at IS NULL
                  AND v.state='published'::content_state
                ORDER BY b.created_at DESC
                """
            )
        ).mappings().all()
        return [BookmarkItem.model_validate(dict(row)) for row in rows]


def bookmark_question(
    slug: str,
    principal: CandidateEngagementWritePrincipal,
    engine: DatabaseEngine,
) -> QuestionEngagementView:
    with principal_transaction(engine, principal) as connection:
        question_id = _question_id(connection, slug)
        connection.execute(
            text(
                """
                INSERT INTO candidate_question_bookmarks (user_id, question_id)
                VALUES (
                    NULLIF(current_setting('rigor.user_id', true), '')::uuid,
                    :question_id
                )
                ON CONFLICT (user_id, question_id) DO NOTHING
                """
            ),
            {"question_id": question_id},
        )
        return QuestionEngagementView(
            question_slug=slug,
            bookmarked=True,
            notes=_notes(connection, question_id=question_id, slug=slug),
        )


def remove_question_bookmark(
    slug: str,
    principal: CandidateEngagementWritePrincipal,
    engine: DatabaseEngine,
) -> Response:
    with principal_transaction(engine, principal) as connection:
        question_id = _question_id(connection, slug)
        connection.execute(
            text(
                """
                DELETE FROM candidate_question_bookmarks
                WHERE question_id=:question_id
                """
            ),
            {"question_id": question_id},
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def create_question_note(
    slug: str,
    payload: QuestionNoteInput,
    principal: CandidateEngagementWritePrincipal,
    engine: DatabaseEngine,
) -> QuestionNoteView:
    body = payload.body.strip()
    if not body:
        raise HTTPException(status_code=422, detail="Note body cannot be blank")
    with principal_transaction(engine, principal) as connection:
        question_id = _question_id(connection, slug)
        row = connection.execute(
            text(
                """
                INSERT INTO candidate_question_notes (user_id, question_id, body)
                VALUES (
                    NULLIF(current_setting('rigor.user_id', true), '')::uuid,
                    :question_id,
                    :body
                )
                RETURNING id, body, created_at, updated_at
                """
            ),
            {"question_id": question_id, "body": body},
        ).mappings().one()
        return QuestionNoteView(
            id=UUID(str(row["id"])),
            question_slug=slug,
            body=str(row["body"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )


def update_question_note(
    slug: str,
    note_id: UUID,
    payload: QuestionNoteInput,
    principal: CandidateEngagementWritePrincipal,
    engine: DatabaseEngine,
) -> QuestionNoteView:
    body = payload.body.strip()
    if not body:
        raise HTTPException(status_code=422, detail="Note body cannot be blank")
    with principal_transaction(engine, principal) as connection:
        question_id = _question_id(connection, slug)
        row = connection.execute(
            text(
                """
                UPDATE candidate_question_notes
                SET body=:body, updated_at=CURRENT_TIMESTAMP
                WHERE id=:note_id AND question_id=:question_id
                RETURNING id, body, created_at, updated_at
                """
            ),
            {"note_id": note_id, "question_id": question_id, "body": body},
        ).mappings().one_or_none()
        if row is None:
            raise HTTPException(status_code=404, detail="Question note not found")
        return QuestionNoteView(
            id=UUID(str(row["id"])),
            question_slug=slug,
            body=str(row["body"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )


def delete_question_note(
    slug: str,
    note_id: UUID,
    principal: CandidateEngagementWritePrincipal,
    engine: DatabaseEngine,
) -> Response:
    with principal_transaction(engine, principal) as connection:
        question_id = _question_id(connection, slug)
        deleted = connection.execute(
            text(
                """
                DELETE FROM candidate_question_notes
                WHERE id=:note_id AND question_id=:question_id
                RETURNING id
                """
            ),
            {"note_id": note_id, "question_id": question_id},
        ).scalar_one_or_none()
        if deleted is None:
            raise HTTPException(status_code=404, detail="Question note not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


router.add_api_route(
    "/questions/{slug}/engagement",
    get_question_engagement,
    methods=["GET"],
    response_model=QuestionEngagementView,
)
router.add_api_route(
    "/candidate/bookmarks",
    list_candidate_bookmarks,
    methods=["GET"],
    response_model=list[BookmarkItem],
)
router.add_api_route(
    "/questions/{slug}/bookmark",
    bookmark_question,
    methods=["PUT"],
    response_model=QuestionEngagementView,
)
router.add_api_route(
    "/questions/{slug}/bookmark",
    remove_question_bookmark,
    methods=["DELETE"],
    status_code=status.HTTP_204_NO_CONTENT,
)
router.add_api_route(
    "/questions/{slug}/notes",
    create_question_note,
    methods=["POST"],
    response_model=QuestionNoteView,
    status_code=status.HTTP_201_CREATED,
)
router.add_api_route(
    "/questions/{slug}/notes/{note_id}",
    update_question_note,
    methods=["PATCH"],
    response_model=QuestionNoteView,
)
router.add_api_route(
    "/questions/{slug}/notes/{note_id}",
    delete_question_note,
    methods=["DELETE"],
    status_code=status.HTTP_204_NO_CONTENT,
)
