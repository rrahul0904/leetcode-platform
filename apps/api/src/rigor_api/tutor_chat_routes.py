from __future__ import annotations

import json
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import Connection, text

from .auth import require_permissions
from .database import DatabaseEngine, principal_transaction
from .schemas import AuthenticatedPrincipal
from .tutor_coach import TutorCoachContext
from .tutor_domain import (
    CandidateLevel,
    SafeCodeContext,
    TutorContextSnapshot,
    TutorContextViolation,
    TutorIntervention,
    TutorMode,
    TutorSurface,
    assert_tutor_context_is_public,
    decide_intervention,
)
from .tutor_mastery import load_tutor_mastery_snapshot
from .tutor_provider import build_tutor_provider_service

router = APIRouter(prefix="/api/v1/tutor", tags=["tutor"])
_CURRENT_USER_SQL = "NULLIF(current_setting('rigor.user_id', true), '')::uuid"

TutorWritePrincipal = Annotated[
    AuthenticatedPrincipal,
    Depends(require_permissions("profile:write")),
]


class TutorChatModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class TutorMessageInput(TutorChatModel):
    message: str = Field(min_length=1, max_length=4_000)
    idempotency_key: str = Field(min_length=1, max_length=120)


class TutorMessageResponse(TutorChatModel):
    session_id: UUID
    reply: str
    provider: str
    model: str
    intervention: TutorIntervention


def _session_context(connection: Connection, session_id: UUID) -> dict[str, Any]:
    row = connection.execute(
        text(
            f"""
            SELECT
                s.id,
                s.mode,
                s.surface,
                s.candidate_level,
                s.status,
                q.slug AS question_slug,
                COALESCE(v.title, s.title, 'Practice session') AS title,
                COALESCE(v.problem_statement, '') AS problem_statement,
                COALESCE(ps.draft_code, '') AS draft_code,
                COALESCE(ps.elapsed_seconds, 0) AS elapsed_seconds,
                COALESCE(ps.runtime::text, 'unknown') AS runtime
            FROM tutor_sessions s
            LEFT JOIN questions q ON q.id=s.question_id
            LEFT JOIN question_versions v ON v.id=q.current_published_version_id
            LEFT JOIN LATERAL (
                SELECT p.draft_code, p.elapsed_seconds, p.runtime
                FROM practice_sessions p
                WHERE p.candidate_id={_CURRENT_USER_SQL}
                  AND p.question_version_id=v.id
                  AND p.state IN (
                    'CREATED'::practice_session_state,
                    'IN_PROGRESS'::practice_session_state,
                    'PAUSED'::practice_session_state
                  )
                ORDER BY p.updated_at DESC
                LIMIT 1
            ) ps ON TRUE
            WHERE s.id=:session_id
              AND s.user_id={_CURRENT_USER_SQL}
            """
        ),
        {"session_id": session_id},
    ).mappings().one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Tutor session not found")
    values = dict(row)
    if str(values["status"]) != "active":
        raise HTTPException(status_code=409, detail="Tutor session has ended")
    return values


def _existing_response(
    connection: Connection,
    session_id: UUID,
    assistant_key: str,
) -> TutorMessageResponse | None:
    row = connection.execute(
        text(
            f"""
            SELECT payload
            FROM tutor_events
            WHERE session_id=:session_id
              AND user_id={_CURRENT_USER_SQL}
              AND idempotency_key=:idempotency_key
              AND event_type='message.assistant'
            """
        ),
        {"session_id": session_id, "idempotency_key": assistant_key},
    ).mappings().one_or_none()
    if row is None:
        return None
    payload = dict(row["payload"])
    return TutorMessageResponse(
        session_id=session_id,
        reply=str(payload["message"]),
        provider=str(payload["provider"]),
        model=str(payload["model"]),
        intervention=TutorIntervention.model_validate(payload["intervention"]),
    )


def _insert_event(
    connection: Connection,
    *,
    session_id: UUID,
    event_type: str,
    idempotency_key: str,
    payload: dict[str, Any],
) -> None:
    assert_tutor_context_is_public(payload)
    encoded = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
    connection.execute(
        text(
            f"""
            INSERT INTO tutor_events (
                user_id, session_id, event_type, idempotency_key, payload
            ) VALUES (
                {_CURRENT_USER_SQL}, :session_id, :event_type,
                :idempotency_key, CAST(:payload AS jsonb)
            )
            ON CONFLICT (session_id, idempotency_key) DO NOTHING
            """
        ),
        {
            "session_id": session_id,
            "event_type": event_type,
            "idempotency_key": idempotency_key,
            "payload": encoded,
        },
    )


@router.post(
    "/sessions/{session_id}/messages",
    response_model=TutorMessageResponse,
)
def send_tutor_message(
    session_id: UUID,
    payload: TutorMessageInput,
    principal: TutorWritePrincipal,
    engine: DatabaseEngine,
) -> TutorMessageResponse:
    """Coach from public workspace state plus aggregate, evidence-backed mastery."""

    user_key = f"{payload.idempotency_key}:user"
    assistant_key = f"{payload.idempotency_key}:assistant"
    with principal_transaction(engine, principal) as connection:
        existing = _existing_response(connection, session_id, assistant_key)
        if existing is not None:
            return existing

        context = _session_context(connection, session_id)
        mode = TutorMode(str(context["mode"]))
        surface = TutorSurface(str(context["surface"]))
        candidate_level = CandidateLevel(str(context["candidate_level"]))
        code = None
        if surface is TutorSurface.CODE:
            code = SafeCodeContext(
                language=str(context["runtime"]),
                source=str(context["draft_code"]),
            )
        snapshot = TutorContextSnapshot(
            mode=mode,
            surface=surface,
            candidate_level=candidate_level,
            question_slug=(
                str(context["question_slug"]) if context["question_slug"] else None
            ),
            public_problem_summary=str(context["problem_statement"]),
            code=code,
            elapsed_seconds=int(context["elapsed_seconds"]),
            user_requested_help=True,
        )
        try:
            assert_tutor_context_is_public(snapshot.model_dump(mode="json"))
        except TutorContextViolation as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

        intervention = decide_intervention(snapshot)
        mastery = load_tutor_mastery_snapshot(connection)
        mastery_public_projection = {
            "competencies": [
                {
                    "slug": item.slug,
                    "name": item.name,
                    "mastery": item.mastery,
                    "confidence": item.confidence,
                    "evidence_count": item.evidence_count,
                }
                for item in mastery.competencies
            ]
        }
        try:
            assert_tutor_context_is_public(mastery_public_projection)
        except TutorContextViolation as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

        coach_context = TutorCoachContext(
            message=payload.message.strip(),
            title=str(context["title"]),
            problem_statement=str(context["problem_statement"]),
            source=str(context["draft_code"]),
            language=str(context["runtime"]),
            elapsed_seconds=int(context["elapsed_seconds"]),
            mode=mode,
            candidate_level=candidate_level,
            intervention=intervention,
            mastery=mastery,
        )
        reply = build_tutor_provider_service().respond(coach_context)

        _insert_event(
            connection,
            session_id=session_id,
            event_type="message.user",
            idempotency_key=user_key,
            payload={"message": payload.message.strip()},
        )
        assistant_payload = {
            "message": reply.text,
            "provider": reply.provider,
            "model": reply.model,
            "intervention": intervention.model_dump(mode="json"),
        }
        _insert_event(
            connection,
            session_id=session_id,
            event_type="message.assistant",
            idempotency_key=assistant_key,
            payload=assistant_payload,
        )
        connection.execute(
            text(
                f"""
                UPDATE tutor_sessions
                SET provider=:provider,
                    model=:model,
                    updated_at=CURRENT_TIMESTAMP
                WHERE id=:session_id
                  AND user_id={_CURRENT_USER_SQL}
                """
            ),
            {
                "session_id": session_id,
                "provider": reply.provider,
                "model": reply.model,
            },
        )
        return TutorMessageResponse(
            session_id=session_id,
            reply=reply.text,
            provider=reply.provider,
            model=reply.model,
            intervention=intervention,
        )
