"""Consent-first, server-timed AI interviewer for employer assessments.

Text-only and no hidden answer key transfer. Human review stays separate.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import Connection, text

from .auth import authenticated_principal
from .database import DatabaseEngine, principal_transaction
from .employer_assessment_routes import _candidate_attempt
from .employer_interview_provider import EmployerInterviewPrompt, employer_interview_provider
from .persistence import audit_event
from .schemas import AuthenticatedPrincipal

router = APIRouter(prefix="/api/v1/assessment-attempts", tags=["employer-ai-interview"])
Principal = Annotated[AuthenticatedPrincipal, Depends(authenticated_principal)]
_USER = "NULLIF(current_setting('rigor.user_id',true),'')::uuid"
CONSENT_VERSION = "employer-ai-text-interview-v1"
MAX_TURNS = 12


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ConsentInput(StrictModel):
    agree_to_ai_processing: bool


class InterviewMessageInput(StrictModel):
    message: str = Field(min_length=1, max_length=2000)
    request_id: str = Field(min_length=12, max_length=120, pattern=r"^[A-Za-z0-9_-]+$")


class InterviewMessageView(StrictModel):
    sequence_number: int
    role: str
    content: str
    request_id: str
    created_at: datetime


class InterviewSessionView(StrictModel):
    id: UUID
    attempt_id: UUID
    status: str
    consent_version: str
    consent_at: datetime
    turn_count: int
    messages: list[InterviewMessageView]
    provider_configured: bool


def _session(conn: Connection, attempt_id: UUID, *, lock: bool = False) -> dict[str, Any]:
    row = conn.execute(
        text(
            f"""SELECT id, attempt_id, candidate_id, organization_id, status,
                       consent_at, consent_version, pending_request_id, turn_count
                FROM employer_ai_interview_sessions
                WHERE attempt_id=:attempt AND candidate_id={_USER}
                {"FOR UPDATE" if lock else ""}"""
        ), {"attempt": attempt_id},
    ).mappings().one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Consented interview session not found")
    return dict(row)


def _messages(conn: Connection, session_id: UUID) -> list[InterviewMessageView]:
    rows = conn.execute(
        text(
            f"""SELECT sequence_number, role, content, request_id, created_at
                FROM employer_ai_interview_messages
                WHERE session_id=:session_id AND candidate_id={_USER}
                ORDER BY sequence_number"""
        ), {"session_id": session_id},
    ).mappings().all()
    return [InterviewMessageView.model_validate(dict(row)) for row in rows]


def _view(conn: Connection, row: dict[str, Any]) -> InterviewSessionView:
    return InterviewSessionView(
        id=row["id"], attempt_id=row["attempt_id"], status=row["status"],
        consent_version=row["consent_version"], consent_at=row["consent_at"],
        turn_count=row["turn_count"], messages=_messages(conn, row["id"]),
        provider_configured=employer_interview_provider() is not None,
    )


def _require_active_attempt(conn: Connection, attempt_id: UUID) -> dict[str, Any]:
    row = _candidate_attempt(conn, attempt_id, lock=True)
    now = conn.execute(text("SELECT CURRENT_TIMESTAMP")).scalar_one()
    if row["status"] != "in_progress" or row["deadline_at"] <= now:
        raise HTTPException(
            status_code=409, detail="The assessment is no longer accepting interview responses"
        )
    return row


@router.post("/{attempt_id}/ai-interview/consent", response_model=InterviewSessionView)
def consent_to_employer_ai_interview(
    attempt_id: UUID, payload: ConsentInput, engine: DatabaseEngine, principal: Principal,
) -> InterviewSessionView:
    if not payload.agree_to_ai_processing:
        raise HTTPException(
            status_code=422, detail="AI processing is opt-in; consent must be explicit"
        )
    with principal_transaction(engine, principal) as conn:
        attempt = _require_active_attempt(conn, attempt_id)
        conn.execute(
            text(
                f"""INSERT INTO employer_ai_interview_sessions
                       (organization_id, attempt_id, candidate_id,
                        consent_at, consent_version)
                    VALUES (:org, :attempt, {_USER}, CURRENT_TIMESTAMP, :version)
                    ON CONFLICT (attempt_id) DO NOTHING"""
            ),
            {
                "org": conn.execute(
                    text(
                        "SELECT organization_id FROM employer_assessment_attempts WHERE id=:id"
                    ),
                    {"id": attempt_id},
                ).scalar_one(),
                "attempt": attempt_id,
                "version": CONSENT_VERSION,
            },
        )
        row = _session(conn, attempt_id)
        if row["status"] != "active":
            raise HTTPException(
                status_code=409, detail="Withdrawn interview consent cannot be reused"
            )
        actor = conn.execute(text(f"SELECT {_USER}")).scalar_one()
        audit_event(
            conn, principal, actor, action="employer.ai_interview_consent",
            resource_type="employer_interview", resource_id=str(row["id"]),
            details={"version": CONSENT_VERSION},
        )
        return _view(conn, row)


@router.get("/{attempt_id}/ai-interview", response_model=InterviewSessionView)
def get_employer_ai_interview(
    attempt_id: UUID, engine: DatabaseEngine, principal: Principal,
) -> InterviewSessionView:
    with principal_transaction(engine, principal) as conn:
        _candidate_attempt(conn, attempt_id)
        row = _session(conn, attempt_id)
        return _view(conn, row)


@router.post("/{attempt_id}/ai-interview/withdraw", response_model=InterviewSessionView)
def withdraw_employer_ai_interview(
    attempt_id: UUID, engine: DatabaseEngine, principal: Principal,
) -> InterviewSessionView:
    with principal_transaction(engine, principal) as conn:
        _candidate_attempt(conn, attempt_id)
        row = _session(conn, attempt_id, lock=True)
        if row["status"] == "active":
            conn.execute(
                text(
                    """UPDATE employer_ai_interview_sessions
                       SET status='withdrawn', pending_request_id=NULL, pending_at=NULL,
                           updated_at=CURRENT_TIMESTAMP
                       WHERE id=:session"""
                ), {"session": row["id"]},
            )
        row = _session(conn, attempt_id)
        actor = conn.execute(text(f"SELECT {_USER}")).scalar_one()
        audit_event(
            conn, principal, actor, action="employer.ai_interview_withdraw",
            resource_type="employer_interview", resource_id=str(row["id"]), details={},
        )
        return _view(conn, row)


@router.post("/{attempt_id}/ai-interview/messages", response_model=InterviewSessionView)
def send_employer_ai_interview_message(
    attempt_id: UUID, payload: InterviewMessageInput,
    engine: DatabaseEngine, principal: Principal,
) -> InterviewSessionView:
    """Reserve one candidate turn, then call the provider outside DB transactions."""
    provider = employer_interview_provider()
    if provider is None:
        raise HTTPException(status_code=503, detail="AI interviewer is not configured")
    request_id = payload.request_id
    user_message = payload.message.strip()
    if not user_message:
        raise HTTPException(status_code=422, detail="A nonempty technical answer is required")

    with principal_transaction(engine, principal) as conn:
        attempt = _require_active_attempt(conn, attempt_id)
        session = _session(conn, attempt_id, lock=True)
        if session["status"] != "active":
            raise HTTPException(status_code=409, detail="AI interview consent has been withdrawn")
        if session["pending_request_id"] is not None:
            raise HTTPException(status_code=409, detail="An interview response is still pending")
        existing = conn.execute(
            text(
                f"""SELECT role, content FROM employer_ai_interview_messages
                    WHERE session_id=:session AND candidate_id={_USER}
                      AND request_id=:request AND role='candidate'"""
            ), {"session": session["id"], "request": request_id},
        ).mappings().one_or_none()
        if existing is not None and existing["content"] != user_message:
            raise HTTPException(status_code=409, detail="Interview request ID payload mismatch")
        if existing is not None:
            interviewer = conn.execute(
                text(
                    f"""SELECT content FROM employer_ai_interview_messages
                        WHERE session_id=:session AND candidate_id={_USER}
                          AND request_id=:request AND role='interviewer'"""
                ), {"session": session["id"], "request": request_id},
            ).scalar_one_or_none()
            if interviewer is not None:
                return _view(conn, session)
        if session["turn_count"] >= MAX_TURNS:
            raise HTTPException(status_code=409, detail="Interview turn limit reached")
        previous = _messages(conn, session["id"])
        if existing is None:
            sequence = session["turn_count"] * 2
            conn.execute(
                text(
                    f"""INSERT INTO employer_ai_interview_messages
                         (session_id, organization_id, candidate_id,
                          sequence_number, role, content, request_id)
                        VALUES (:session, :org, {_USER},
                                :sequence, 'candidate', :message, :request)"""
                ),
                {
                    "session": session["id"],
                    "org": session["organization_id"],
                    "sequence": sequence,
                    "message": user_message,
                    "request": request_id,
                },
            )
        conn.execute(
            text(
                """UPDATE employer_ai_interview_sessions
                   SET pending_request_id=:request, pending_at=CURRENT_TIMESTAMP
                   WHERE id=:session"""
            ), {"session": session["id"], "request": request_id},
        )
        prompt = EmployerInterviewPrompt(
            questions=[
                str(q["prompt"])[:1200]
                for q in attempt["candidate_blueprint"]["questions"][:5]
            ],
            messages=[
                {"role": turn.role, "content": turn.content[:1500]}
                for turn in previous[-8:]
            ],
            candidate_message=user_message,
        )

    try:
        reply = provider.followup(prompt)
    except Exception as exc:
        with principal_transaction(engine, principal) as conn:
            row = _session(conn, attempt_id, lock=True)
            if row["pending_request_id"] == request_id:
                conn.execute(
                    text(
                        """UPDATE employer_ai_interview_sessions
                           SET pending_request_id=NULL, pending_at=NULL
                           WHERE id=:session"""
                    ), {"session": row["id"]},
                )
        raise HTTPException(status_code=502, detail="AI interviewer unavailable") from exc

    with principal_transaction(engine, principal) as conn:
        _require_active_attempt(conn, attempt_id)
        row = _session(conn, attempt_id, lock=True)
        if row["status"] != "active" or row["pending_request_id"] != request_id:
            raise HTTPException(status_code=409, detail="Interview session changed during reply")
        conn.execute(
            text(
                f"""INSERT INTO employer_ai_interview_messages
                     (session_id, organization_id, candidate_id, sequence_number,
                      role, content, request_id)
                    VALUES (:session, :org, {_USER}, :sequence,
                            'interviewer', :message, :request)"""
            ),
            {
                "session": row["id"], "org": row["organization_id"],
                "sequence": row["turn_count"] * 2 + 1,
                "message": reply, "request": request_id,
            },
        )
        conn.execute(
            text(
                """UPDATE employer_ai_interview_sessions
                   SET pending_request_id=NULL, pending_at=NULL,
                       turn_count=turn_count+1, updated_at=CURRENT_TIMESTAMP,
                       status=CASE WHEN turn_count>=11 THEN 'completed' ELSE status END
                   WHERE id=:session"""
            ), {"session": row["id"]},
        )
        return _view(conn, _session(conn, attempt_id))
