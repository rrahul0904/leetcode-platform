from __future__ import annotations

import json
from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import Connection, text

from .auth import require_permissions
from .database import DatabaseEngine, principal_transaction
from .schemas import AuthenticatedPrincipal
from .tutor_domain import (
    CandidateLevel,
    TutorContextSnapshot,
    TutorContextViolation,
    TutorIntervention,
    TutorMode,
    TutorSurface,
    assert_tutor_context_is_public,
    decide_intervention,
)

router = APIRouter(prefix="/api/v1/tutor", tags=["tutor"])

_CURRENT_USER_SQL = "NULLIF(current_setting('rigor.user_id', true), '')::uuid"
_MAX_EVENT_PAYLOAD_BYTES = 64 * 1024


class TutorRouteModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class TutorCapabilities(TutorRouteModel):
    text_sessions: bool
    code_context: bool
    whiteboard_context: bool
    adaptive_interventions: bool
    realtime_voice: bool
    persistent_sessions: bool
    mastery_updates: bool
    hidden_evaluation_exposed: bool


class TutorSessionCreate(TutorRouteModel):
    mode: TutorMode
    surface: TutorSurface
    candidate_level: CandidateLevel
    question_slug: str | None = Field(default=None, min_length=1, max_length=200)
    title: str | None = Field(default=None, min_length=1, max_length=240)


class TutorSessionView(TutorRouteModel):
    id: UUID
    mode: TutorMode
    surface: TutorSurface
    candidate_level: CandidateLevel
    status: str
    question_slug: str | None = None
    title: str | None = None
    provider: str | None = None
    model: str | None = None
    summary: str | None = None
    started_at: datetime
    updated_at: datetime
    ended_at: datetime | None = None


class TutorEventInput(TutorRouteModel):
    event_type: str = Field(min_length=1, max_length=120)
    idempotency_key: str = Field(min_length=1, max_length=160)
    payload: dict[str, Any] = Field(default_factory=dict)


class TutorEventView(TutorRouteModel):
    id: UUID
    session_id: UUID
    event_type: str
    idempotency_key: str
    payload: dict[str, Any]
    created_at: datetime


class TutorSessionEndInput(TutorRouteModel):
    summary: str | None = Field(default=None, max_length=20_000)


TutorReadPrincipal = Annotated[
    AuthenticatedPrincipal,
    Depends(require_permissions("profile:read")),
]
TutorWritePrincipal = Annotated[
    AuthenticatedPrincipal,
    Depends(require_permissions("profile:write")),
]


def _published_question_id(connection: Connection, slug: str | None) -> UUID | None:
    if slug is None:
        return None
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


def _session_view(row: Any) -> TutorSessionView:
    return TutorSessionView(
        id=UUID(str(row["id"])),
        mode=TutorMode(str(row["mode"])),
        surface=TutorSurface(str(row["surface"])),
        candidate_level=CandidateLevel(str(row["candidate_level"])),
        status=str(row["status"]),
        question_slug=str(row["question_slug"]) if row["question_slug"] else None,
        title=str(row["title"]) if row["title"] else None,
        provider=str(row["provider"]) if row["provider"] else None,
        model=str(row["model"]) if row["model"] else None,
        summary=str(row["summary"]) if row["summary"] else None,
        started_at=row["started_at"],
        updated_at=row["updated_at"],
        ended_at=row["ended_at"],
    )


def _session_select_sql(*, where: str) -> str:
    return f"""
        SELECT
            s.id,
            s.mode,
            s.surface,
            s.candidate_level,
            s.status,
            q.slug AS question_slug,
            s.title,
            s.provider,
            s.model,
            s.summary,
            s.started_at,
            s.updated_at,
            s.ended_at
        FROM tutor_sessions s
        LEFT JOIN questions q ON q.id=s.question_id
        WHERE s.user_id={_CURRENT_USER_SQL}
          AND {where}
    """


def _require_active_session(connection: Connection, session_id: UUID) -> None:
    status_value = connection.execute(
        text(
            f"""
            SELECT status
            FROM tutor_sessions
            WHERE id=:session_id
              AND user_id={_CURRENT_USER_SQL}
            """
        ),
        {"session_id": session_id},
    ).scalar_one_or_none()
    if status_value is None:
        raise HTTPException(status_code=404, detail="Tutor session not found")
    if str(status_value) != "active":
        raise HTTPException(status_code=409, detail="Tutor session has ended")


@router.get("/capabilities", response_model=TutorCapabilities)
def get_tutor_capabilities(_principal: TutorReadPrincipal) -> TutorCapabilities:
    """Return server-authoritative rollout state for candidate tutor features."""

    return TutorCapabilities(
        text_sessions=True,
        code_context=True,
        whiteboard_context=True,
        adaptive_interventions=True,
        realtime_voice=False,
        persistent_sessions=True,
        mastery_updates=False,
        hidden_evaluation_exposed=False,
    )


@router.post("/interventions/decide", response_model=TutorIntervention)
def decide_tutor_intervention(
    payload: TutorContextSnapshot,
    _principal: TutorReadPrincipal,
) -> TutorIntervention:
    """Apply the deterministic intervention gate before any model is allowed to speak."""

    return decide_intervention(payload)


@router.post("/sessions", response_model=TutorSessionView, status_code=201)
def create_tutor_session(
    payload: TutorSessionCreate,
    principal: TutorWritePrincipal,
    engine: DatabaseEngine,
) -> TutorSessionView:
    with principal_transaction(engine, principal) as connection:
        question_id = _published_question_id(connection, payload.question_slug)
        row = connection.execute(
            text(
                f"""
                INSERT INTO tutor_sessions (
                    user_id, question_id, mode, surface, candidate_level, title
                )
                VALUES (
                    {_CURRENT_USER_SQL}, :question_id, :mode, :surface, :candidate_level, :title
                )
                RETURNING id
                """
            ),
            {
                "question_id": question_id,
                "mode": payload.mode.value,
                "surface": payload.surface.value,
                "candidate_level": payload.candidate_level.value,
                "title": payload.title,
            },
        ).mappings().one()
        session_row = connection.execute(
            text(_session_select_sql(where="s.id=:session_id")),
            {"session_id": row["id"]},
        ).mappings().one()
        return _session_view(session_row)


@router.get("/sessions", response_model=list[TutorSessionView])
def list_tutor_sessions(
    principal: TutorReadPrincipal,
    engine: DatabaseEngine,
) -> list[TutorSessionView]:
    with principal_transaction(engine, principal) as connection:
        rows = connection.execute(
            text(
                _session_select_sql(where="TRUE")
                + " ORDER BY s.updated_at DESC, s.started_at DESC LIMIT 50"
            )
        ).mappings().all()
        return [_session_view(row) for row in rows]


@router.get("/sessions/{session_id}", response_model=TutorSessionView)
def get_tutor_session(
    session_id: UUID,
    principal: TutorReadPrincipal,
    engine: DatabaseEngine,
) -> TutorSessionView:
    with principal_transaction(engine, principal) as connection:
        row = connection.execute(
            text(_session_select_sql(where="s.id=:session_id")),
            {"session_id": session_id},
        ).mappings().one_or_none()
        if row is None:
            raise HTTPException(status_code=404, detail="Tutor session not found")
        return _session_view(row)


@router.post("/sessions/{session_id}/events", response_model=TutorEventView, status_code=201)
def append_tutor_event(
    session_id: UUID,
    payload: TutorEventInput,
    principal: TutorWritePrincipal,
    engine: DatabaseEngine,
) -> TutorEventView:
    try:
        assert_tutor_context_is_public(payload.payload)
    except TutorContextViolation as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    payload_json = json.dumps(payload.payload, separators=(",", ":"), ensure_ascii=False)
    if len(payload_json.encode("utf-8")) > _MAX_EVENT_PAYLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Tutor event payload exceeds 64 KiB")

    with principal_transaction(engine, principal) as connection:
        _require_active_session(connection, session_id)
        row = connection.execute(
            text(
                f"""
                INSERT INTO tutor_events (
                    user_id, session_id, event_type, idempotency_key, payload
                )
                VALUES (
                    {_CURRENT_USER_SQL}, :session_id, :event_type,
                    :idempotency_key, CAST(:payload AS jsonb)
                )
                ON CONFLICT (session_id, idempotency_key) DO UPDATE
                SET idempotency_key=EXCLUDED.idempotency_key
                RETURNING id, session_id, event_type, idempotency_key, payload, created_at
                """
            ),
            {
                "session_id": session_id,
                "event_type": payload.event_type,
                "idempotency_key": payload.idempotency_key,
                "payload": payload_json,
            },
        ).mappings().one()
        connection.execute(
            text(
                f"""
                UPDATE tutor_sessions
                SET updated_at=CURRENT_TIMESTAMP
                WHERE id=:session_id
                  AND user_id={_CURRENT_USER_SQL}
                """
            ),
            {"session_id": session_id},
        )
        return TutorEventView(
            id=UUID(str(row["id"])),
            session_id=UUID(str(row["session_id"])),
            event_type=str(row["event_type"]),
            idempotency_key=str(row["idempotency_key"]),
            payload=dict(row["payload"]),
            created_at=row["created_at"],
        )


@router.get("/sessions/{session_id}/events", response_model=list[TutorEventView])
def list_tutor_events(
    session_id: UUID,
    principal: TutorReadPrincipal,
    engine: DatabaseEngine,
) -> list[TutorEventView]:
    with principal_transaction(engine, principal) as connection:
        exists = connection.execute(
            text(
                f"""
                SELECT 1
                FROM tutor_sessions
                WHERE id=:session_id
                  AND user_id={_CURRENT_USER_SQL}
                """
            ),
            {"session_id": session_id},
        ).scalar_one_or_none()
        if exists is None:
            raise HTTPException(status_code=404, detail="Tutor session not found")
        rows = connection.execute(
            text(
                f"""
                SELECT id, session_id, event_type, idempotency_key, payload, created_at
                FROM tutor_events
                WHERE session_id=:session_id
                  AND user_id={_CURRENT_USER_SQL}
                ORDER BY created_at ASC, id ASC
                LIMIT 1000
                """
            ),
            {"session_id": session_id},
        ).mappings().all()
        return [
            TutorEventView(
                id=UUID(str(row["id"])),
                session_id=UUID(str(row["session_id"])),
                event_type=str(row["event_type"]),
                idempotency_key=str(row["idempotency_key"]),
                payload=dict(row["payload"]),
                created_at=row["created_at"],
            )
            for row in rows
        ]


@router.post("/sessions/{session_id}/end", response_model=TutorSessionView)
def end_tutor_session(
    session_id: UUID,
    payload: TutorSessionEndInput,
    principal: TutorWritePrincipal,
    engine: DatabaseEngine,
) -> TutorSessionView:
    with principal_transaction(engine, principal) as connection:
        result = connection.execute(
            text(
                f"""
                UPDATE tutor_sessions
                SET status='ended',
                    summary=:summary,
                    ended_at=CURRENT_TIMESTAMP,
                    updated_at=CURRENT_TIMESTAMP
                WHERE id=:session_id
                  AND user_id={_CURRENT_USER_SQL}
                  AND status='active'
                RETURNING id
                """
            ),
            {"session_id": session_id, "summary": payload.summary},
        ).mappings().one_or_none()
        if result is None:
            existing = connection.execute(
                text(
                    f"""
                    SELECT status
                    FROM tutor_sessions
                    WHERE id=:session_id
                      AND user_id={_CURRENT_USER_SQL}
                    """
                ),
                {"session_id": session_id},
            ).scalar_one_or_none()
            if existing is None:
                raise HTTPException(status_code=404, detail="Tutor session not found")
            if str(existing) != "ended":
                raise HTTPException(status_code=409, detail="Tutor session cannot be ended")
        row = connection.execute(
            text(_session_select_sql(where="s.id=:session_id")),
            {"session_id": session_id},
        ).mappings().one()
        return _session_view(row)
