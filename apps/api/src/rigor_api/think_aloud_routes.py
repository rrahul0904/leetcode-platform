from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Literal, cast
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import Connection, text

from .auth import require_permissions
from .database import DatabaseEngine, principal_transaction
from .mock_interview_domain import template_for
from .mock_interview_routes import (
    MockInterviewCreate,
    MockInterviewResponseInput,
    MockInterviewSessionView,
    _detail,
    _insert_message,
    _session_row,
    answer_mock_interview,
    create_mock_interview,
)
from .schemas import AuthenticatedPrincipal, MockInterviewState

router = APIRouter(prefix="/api/v1/think-aloud", tags=["think-aloud"])

ThinkAloudMode = Literal["practice", "assessment"]
FloorOwner = Literal["candidate", "interviewer", "coach", "none"]
EventType = Literal[
    "candidate_silence",
    "candidate_interrupt",
    "provider_disconnected",
    "provider_reconnected",
]
CanvasMutationKind = Literal[
    "add_component",
    "update_component",
    "remove_component",
    "connect",
    "note",
]

_ALLOWED_FOCUSES = {"system-design", "data-engineering", "ai-architecture"}
_CURRENT_USER_SQL = "NULLIF(current_setting('rigor.user_id', true), '')::uuid"


class ThinkAloudModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ThinkAloudCreate(ThinkAloudModel):
    focus: str = "system-design"
    target_role: str = Field(min_length=2, max_length=160)
    mode: ThinkAloudMode = "practice"


class ThinkAloudTurnInput(ThinkAloudModel):
    content: str = Field(min_length=1, max_length=50_000)


class ThinkAloudEventInput(ThinkAloudModel):
    event_type: EventType
    payload: dict[str, object] = Field(default_factory=dict)


class ThinkAloudCoachingInput(ThinkAloudModel):
    question: str | None = Field(default=None, max_length=2_000)


class ThinkAloudCanvasMutationInput(ThinkAloudModel):
    kind: CanvasMutationKind
    label: str = Field(min_length=1, max_length=180)
    component_type: str | None = Field(default=None, max_length=80)
    payload: dict[str, object] = Field(default_factory=dict)


class ThinkAloudEventView(ThinkAloudModel):
    sequence_number: int
    role: str
    phase: str
    event_type: str
    content: str
    payload: dict[str, object]
    created_at: datetime


class ThinkAloudControlState(ThinkAloudModel):
    session_id: UUID
    mode: ThinkAloudMode
    floor_owner: FloorOwner
    coaching_active: bool
    provider_connected: bool
    events: list[ThinkAloudEventView]
    canvas: list[ThinkAloudEventView]


class ThinkAloudSessionView(ThinkAloudModel):
    session: MockInterviewSessionView
    control: ThinkAloudControlState


ThinkReadPrincipal = Annotated[
    AuthenticatedPrincipal,
    Depends(require_permissions("submission:read-own")),
]
ThinkWritePrincipal = Annotated[
    AuthenticatedPrincipal,
    Depends(require_permissions("submission:create")),
]
ThinkIdempotencyHeader = Annotated[
    str,
    Header(alias="Idempotency-Key", min_length=8, max_length=160),
]


def _control_rows(connection: Connection, session_id: UUID) -> list[Any]:
    return connection.execute(
        text(
            """
            SELECT sequence_number, role, phase, content, evidence, created_at
            FROM mock_interview_messages
            WHERE session_id=:session_id
              AND role IN ('system', 'coach', 'canvas')
            ORDER BY sequence_number
            """
        ),
        {"session_id": session_id},
    ).mappings().all()


def _event_payload(row: Any) -> dict[str, object]:
    raw = row["evidence"]
    if not isinstance(raw, dict):
        return {}
    return cast(dict[str, object], raw)


def _find_event_by_key(
    connection: Connection,
    session_id: UUID,
    idempotency_key: str,
) -> Any | None:
    return connection.execute(
        text(
            """
            SELECT sequence_number, role, phase, content, evidence, created_at
            FROM mock_interview_messages
            WHERE session_id=:session_id
              AND role IN ('system', 'coach', 'canvas')
              AND evidence->>'idempotency_key'=:idempotency_key
            ORDER BY sequence_number DESC
            LIMIT 1
            """
        ),
        {"session_id": session_id, "idempotency_key": idempotency_key},
    ).mappings().one_or_none()


def _mode_from_rows(rows: list[Any]) -> ThinkAloudMode:
    for row in rows:
        payload = _event_payload(row)
        if payload.get("event_type") == "think_aloud_initialized":
            mode = str(payload.get("mode") or "practice")
            return "assessment" if mode == "assessment" else "practice"
    return "practice"


def _control_state(
    connection: Connection,
    session_id: UUID,
) -> ThinkAloudControlState:
    session_row = _session_row(connection, session_id)
    rows = _control_rows(connection, session_id)
    mode = _mode_from_rows(rows)
    status = MockInterviewState(str(session_row["status"]))
    floor: FloorOwner = "candidate" if status is MockInterviewState.in_progress else "none"
    coaching_active = False
    provider_connected = True
    events: list[ThinkAloudEventView] = []
    canvas: list[ThinkAloudEventView] = []

    for row in rows:
        payload = _event_payload(row)
        event_type = str(payload.get("event_type") or "control_event")
        view = ThinkAloudEventView(
            sequence_number=int(row["sequence_number"]),
            role=str(row["role"]),
            phase=str(row["phase"]),
            event_type=event_type,
            content=str(row["content"]),
            payload={
                str(key): value
                for key, value in payload.items()
                if key not in {"event_type", "idempotency_key"}
            },
            created_at=row["created_at"],
        )
        events.append(view)
        if event_type == "canvas_mutation":
            canvas.append(view)
        elif event_type == "candidate_interrupt":
            floor = "candidate"
        elif event_type == "turn_committed":
            floor = "candidate" if status is MockInterviewState.in_progress else "none"
        elif event_type == "coaching_started":
            coaching_active = True
            floor = "coach"
        elif event_type == "coaching_resumed":
            coaching_active = False
            floor = "candidate"
        elif event_type == "provider_disconnected":
            provider_connected = False
        elif event_type == "provider_reconnected":
            provider_connected = True
        # candidate_silence intentionally does not modify floor ownership.

    if status in {MockInterviewState.completed, MockInterviewState.cancelled}:
        floor = "none"
        coaching_active = False
    elif status is MockInterviewState.paused and not coaching_active:
        floor = "none"

    return ThinkAloudControlState(
        session_id=session_id,
        mode=mode,
        floor_owner=floor,
        coaching_active=coaching_active,
        provider_connected=provider_connected,
        events=events,
        canvas=canvas,
    )


def _composite(connection: Connection, session_id: UUID) -> ThinkAloudSessionView:
    return ThinkAloudSessionView(
        session=_detail(connection, session_id),
        control=_control_state(connection, session_id),
    )


def _ensure_mutable(row: Any) -> MockInterviewState:
    status = MockInterviewState(str(row["status"]))
    if status in {MockInterviewState.completed, MockInterviewState.cancelled}:
        raise HTTPException(
            status_code=409,
            detail="Finalized Think Aloud sessions are immutable.",
        )
    return status


def _initialize(
    connection: Connection,
    *,
    session_id: UUID,
    mode: ThinkAloudMode,
    idempotency_key: str,
) -> None:
    row = _session_row(connection, session_id, lock=True)
    _ensure_mutable(row)
    rows = _control_rows(connection, session_id)
    for event in rows:
        payload = _event_payload(event)
        if payload.get("event_type") != "think_aloud_initialized":
            continue
        existing_mode = str(payload.get("mode") or "practice")
        if existing_mode != mode:
            raise HTTPException(
                status_code=409,
                detail="This Think Aloud session was initialized with a different mode.",
            )
        return
    _insert_message(
        connection,
        session_id=session_id,
        role="system",
        phase=str(row["current_phase"]),
        content=f"Think Aloud {mode} controls initialized.",
        evidence={
            "event_type": "think_aloud_initialized",
            "mode": mode,
            "idempotency_key": f"think-init:{idempotency_key}",
            "turn_policy": "explicit_candidate_commit",
            "silence_yields_floor": False,
        },
    )


def _phase_guidance(row: Any, question: str | None) -> str:
    template = template_for(str(row["source_id"]))
    phase_slug = str(row["current_phase"])
    phase = None
    if template is not None:
        phase = next((item for item in template.phases if item.slug == phase_slug), None)
    anchors: list[str] = []
    if phase is not None:
        anchors = [group[0] for group in phase.concept_groups[:4] if group]
    focus = ", ".join(anchors) if anchors else "requirements, trade-offs, failure modes, and evidence"
    question_clause = f" Your question: {question.strip()}" if question and question.strip() else ""
    return (
        "Coach pause: structure your next response before continuing the interview. "
        "State assumptions first, make one concrete design decision, explain the trade-off, "
        f"and test it against failure or scale. Useful anchors for this phase: {focus}."
        f"{question_clause}"
    )


@router.post("/sessions", response_model=ThinkAloudSessionView, status_code=201)
def create_think_aloud_session(
    request: ThinkAloudCreate,
    principal: ThinkWritePrincipal,
    engine: DatabaseEngine,
    idempotency_key: ThinkIdempotencyHeader,
) -> ThinkAloudSessionView:
    focus = request.focus.strip()
    if focus not in _ALLOWED_FOCUSES:
        raise HTTPException(
            status_code=422,
            detail="Think Aloud currently supports system-design, data-engineering, and ai-architecture.",
        )
    created = create_mock_interview(
        MockInterviewCreate(focus=focus, target_role=request.target_role),
        principal,
        engine,
        idempotency_key,
    )
    with principal_transaction(engine, principal) as connection:
        _initialize(
            connection,
            session_id=created.id,
            mode=request.mode,
            idempotency_key=idempotency_key,
        )
        return _composite(connection, created.id)


@router.get("/sessions/{session_id}", response_model=ThinkAloudSessionView)
def get_think_aloud_session(
    session_id: UUID,
    principal: ThinkReadPrincipal,
    engine: DatabaseEngine,
) -> ThinkAloudSessionView:
    with principal_transaction(engine, principal) as connection:
        return _composite(connection, session_id)


@router.post(
    "/sessions/{session_id}/turns/commit",
    response_model=ThinkAloudSessionView,
)
def commit_candidate_turn(
    session_id: UUID,
    request: ThinkAloudTurnInput,
    principal: ThinkWritePrincipal,
    engine: DatabaseEngine,
    idempotency_key: ThinkIdempotencyHeader,
) -> ThinkAloudSessionView:
    content = request.content.strip()
    if not content:
        raise HTTPException(status_code=422, detail="Candidate turn cannot be empty.")

    with principal_transaction(engine, principal) as connection:
        row = _session_row(connection, session_id, lock=True)
        existing = _find_event_by_key(connection, session_id, idempotency_key)
        if existing is not None:
            return _composite(connection, session_id)
        status = _ensure_mutable(row)
        state = _control_state(connection, session_id)
        if status is not MockInterviewState.in_progress or state.floor_owner != "candidate":
            raise HTTPException(
                status_code=409,
                detail="The candidate may commit only while owning the floor in an active interview.",
            )

    updated = answer_mock_interview(
        session_id,
        MockInterviewResponseInput(content=content),
        principal,
        engine,
        idempotency_key,
    )
    with principal_transaction(engine, principal) as connection:
        if _find_event_by_key(connection, session_id, idempotency_key) is None:
            _insert_message(
                connection,
                session_id=session_id,
                role="system",
                phase=updated.current_phase,
                content="Candidate explicitly yielded the floor after committing a response.",
                evidence={
                    "event_type": "turn_committed",
                    "idempotency_key": idempotency_key,
                    "explicit": True,
                    "next_status": updated.status.value,
                },
            )
        return _composite(connection, session_id)


@router.post("/sessions/{session_id}/events", response_model=ThinkAloudSessionView)
def record_think_aloud_event(
    session_id: UUID,
    request: ThinkAloudEventInput,
    principal: ThinkWritePrincipal,
    engine: DatabaseEngine,
    idempotency_key: ThinkIdempotencyHeader,
) -> ThinkAloudSessionView:
    with principal_transaction(engine, principal) as connection:
        row = _session_row(connection, session_id, lock=True)
        if _find_event_by_key(connection, session_id, idempotency_key) is not None:
            return _composite(connection, session_id)
        _ensure_mutable(row)
        state = _control_state(connection, session_id)
        if request.event_type == "candidate_silence" and state.floor_owner != "candidate":
            raise HTTPException(status_code=409, detail="Silence can be recorded only while the candidate owns the floor.")
        _insert_message(
            connection,
            session_id=session_id,
            role="system",
            phase=str(row["current_phase"]),
            content=request.event_type.replace("_", " "),
            evidence={
                "event_type": request.event_type,
                "idempotency_key": idempotency_key,
                "payload": request.payload,
            },
        )
        return _composite(connection, session_id)


@router.post("/sessions/{session_id}/canvas", response_model=ThinkAloudSessionView)
def mutate_think_aloud_canvas(
    session_id: UUID,
    request: ThinkAloudCanvasMutationInput,
    principal: ThinkWritePrincipal,
    engine: DatabaseEngine,
    idempotency_key: ThinkIdempotencyHeader,
) -> ThinkAloudSessionView:
    with principal_transaction(engine, principal) as connection:
        row = _session_row(connection, session_id, lock=True)
        if _find_event_by_key(connection, session_id, idempotency_key) is not None:
            return _composite(connection, session_id)
        _ensure_mutable(row)
        _insert_message(
            connection,
            session_id=session_id,
            role="canvas",
            phase=str(row["current_phase"]),
            content=request.label.strip(),
            evidence={
                "event_type": "canvas_mutation",
                "idempotency_key": idempotency_key,
                "kind": request.kind,
                "label": request.label.strip(),
                "component_type": request.component_type,
                "payload": request.payload,
            },
        )
        return _composite(connection, session_id)


@router.post("/sessions/{session_id}/coaching", response_model=ThinkAloudSessionView)
def start_think_aloud_coaching(
    session_id: UUID,
    request: ThinkAloudCoachingInput,
    principal: ThinkWritePrincipal,
    engine: DatabaseEngine,
    idempotency_key: ThinkIdempotencyHeader,
) -> ThinkAloudSessionView:
    with principal_transaction(engine, principal) as connection:
        row = _session_row(connection, session_id, lock=True)
        if _find_event_by_key(connection, session_id, idempotency_key) is not None:
            return _composite(connection, session_id)
        status = _ensure_mutable(row)
        state = _control_state(connection, session_id)
        if state.mode == "assessment":
            raise HTTPException(status_code=409, detail="Coaching is disabled in assessment mode.")
        if status is not MockInterviewState.in_progress:
            raise HTTPException(status_code=409, detail="Coaching can start only during an active interview.")
        if state.coaching_active:
            raise HTTPException(status_code=409, detail="Coaching is already active.")
        guidance = _phase_guidance(row, request.question)
        connection.execute(
            text(
                f"""
                UPDATE mock_interview_sessions
                SET status='PAUSED'::mock_interview_state,
                    updated_at=CURRENT_TIMESTAMP
                WHERE id=:session_id
                  AND candidate_id={_CURRENT_USER_SQL}
                """
            ),
            {"session_id": session_id},
        )
        _insert_message(
            connection,
            session_id=session_id,
            role="coach",
            phase=str(row["current_phase"]),
            content=guidance,
            evidence={
                "event_type": "coaching_started",
                "idempotency_key": idempotency_key,
                "question": request.question,
            },
        )
        return _composite(connection, session_id)


@router.post("/sessions/{session_id}/coaching/resume", response_model=ThinkAloudSessionView)
def resume_think_aloud_coaching(
    session_id: UUID,
    principal: ThinkWritePrincipal,
    engine: DatabaseEngine,
    idempotency_key: ThinkIdempotencyHeader,
) -> ThinkAloudSessionView:
    with principal_transaction(engine, principal) as connection:
        row = _session_row(connection, session_id, lock=True)
        if _find_event_by_key(connection, session_id, idempotency_key) is not None:
            return _composite(connection, session_id)
        status = _ensure_mutable(row)
        state = _control_state(connection, session_id)
        if state.mode == "assessment":
            raise HTTPException(status_code=409, detail="Coaching is disabled in assessment mode.")
        if status is not MockInterviewState.paused or not state.coaching_active:
            raise HTTPException(status_code=409, detail="There is no active coaching pause to resume.")
        connection.execute(
            text(
                f"""
                UPDATE mock_interview_sessions
                SET status='IN_PROGRESS'::mock_interview_state,
                    updated_at=CURRENT_TIMESTAMP
                WHERE id=:session_id
                  AND candidate_id={_CURRENT_USER_SQL}
                """
            ),
            {"session_id": session_id},
        )
        _insert_message(
            connection,
            session_id=session_id,
            role="system",
            phase=str(row["current_phase"]),
            content="Coaching pause ended; candidate owns the floor again.",
            evidence={
                "event_type": "coaching_resumed",
                "idempotency_key": idempotency_key,
            },
        )
        return _composite(connection, session_id)
