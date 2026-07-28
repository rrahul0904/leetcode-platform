from __future__ import annotations

import json
from typing import Annotated, Any, cast
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import Connection, text

from .auth import require_permissions
from .database import DatabaseEngine, principal_transaction
from .schemas import (
    AuthenticatedPrincipal,
    PracticeHint,
    PracticeSessionCreateRequest,
    PracticeSessionEventInput,
    PracticeSessionPatch,
    PracticeSessionState,
    PracticeSessionView,
    SubmissionRuntime,
)

router = APIRouter(prefix="/api/v1", tags=["practice"])


class PracticeSessionNotFoundError(Exception):
    pass


class PracticeStateTransitionError(Exception):
    pass


def candidate_id(connection: Connection) -> UUID:
    value = connection.execute(
        text("SELECT NULLIF(current_setting('rigor.user_id', true), '')::uuid")
    ).scalar_one()
    if value is None:
        raise RuntimeError("Candidate database context is unavailable")
    return UUID(str(value))


def published_question_payload(connection: Connection, slug: str) -> dict[str, Any]:
    row = (
        connection.execute(
            text(
                """
                SELECT q.id AS question_id, q.slug, v.id AS question_version_id,
                       v.title, v.version AS publication_version,
                       v.structured_content
                FROM questions q
                JOIN question_versions v ON v.id=q.current_published_version_id
                WHERE q.slug=:slug
                  AND q.archived_at IS NULL
                  AND v.state='published'::content_state
                """
            ),
            {"slug": slug},
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        raise PracticeSessionNotFoundError
    return dict(row)


def question_mode(payload: dict[str, Any]) -> dict[str, Any]:
    structured = payload.get("structured_content")
    if not isinstance(structured, dict):
        return {}
    mode = cast(dict[str, Any], structured).get("mode_specification")
    return cast(dict[str, Any], mode) if isinstance(mode, dict) else {}


def question_tests(payload: dict[str, Any], *, public_only: bool) -> list[dict[str, Any]]:
    tests_value = question_mode(payload).get("tests", [])
    if not isinstance(tests_value, list):
        return []
    tests = [
        cast(dict[str, Any], item)
        for item in cast(list[object], tests_value)
        if isinstance(item, dict)
    ]
    if public_only:
        return [test for test in tests if test.get("visibility") == "public"]
    return tests


def question_hints(payload: dict[str, Any]) -> list[dict[str, Any]]:
    structured = payload.get("structured_content")
    if not isinstance(structured, dict):
        return []
    hints_value = cast(dict[str, Any], structured).get("hints", [])
    if not isinstance(hints_value, list):
        return []
    return [
        cast(dict[str, Any], item)
        for item in cast(list[object], hints_value)
        if isinstance(item, dict)
    ]


class PracticeSessionRepository:
    def __init__(self, connection: Connection) -> None:
        self._connection = connection

    def create(
        self,
        principal: AuthenticatedPrincipal,
        request: PracticeSessionCreateRequest,
    ) -> PracticeSessionView:
        if request.runtime != SubmissionRuntime.python:
            raise PracticeStateTransitionError(
                "The Python practice milestone currently accepts python3.13 only."
            )
        question = published_question_payload(self._connection, request.question_slug)
        mode = question_mode(question)
        starter_code = str(mode.get("starter_code") or "")
        existing = self._connection.execute(
            text(
                """
                    SELECT ps.id
                    FROM practice_sessions ps
                    WHERE ps.candidate_id=NULLIF(
                        current_setting('rigor.user_id', true), ''
                    )::uuid
                      AND ps.question_version_id=:question_version_id
                      AND ps.runtime=:runtime
                      AND ps.state IN (
                        'CREATED'::practice_session_state,
                        'IN_PROGRESS'::practice_session_state,
                        'PAUSED'::practice_session_state
                      )
                    ORDER BY ps.updated_at DESC
                    LIMIT 1
                    """
            ),
            {
                "question_version_id": question["question_version_id"],
                "runtime": request.runtime.value,
            },
        ).scalar_one_or_none()
        if existing is not None:
            return self.get(UUID(str(existing)))
        session_id = self._connection.execute(
            text(
                """
                INSERT INTO practice_sessions (
                    organization_id, candidate_id, question_version_id,
                    session_type, state, runtime, draft_code,
                    started_at, last_activity_at
                ) VALUES (
                    CAST(NULLIF(:organization_id, '') AS uuid),
                    NULLIF(current_setting('rigor.user_id', true), '')::uuid,
                    :question_version_id,
                    'HOSTED_QUESTION',
                    'IN_PROGRESS'::practice_session_state,
                    :runtime,
                    :draft_code,
                    CURRENT_TIMESTAMP,
                    CURRENT_TIMESTAMP
                )
                RETURNING id
                """
            ),
            {
                "organization_id": principal.organization_id or "",
                "question_version_id": question["question_version_id"],
                "runtime": request.runtime.value,
                "draft_code": starter_code,
            },
        ).scalar_one()
        self.append_event(
            UUID(str(session_id)),
            PracticeSessionEventInput(
                event_type="SESSION_STARTED",
                payload={"question_slug": request.question_slug},
            ),
        )
        return self.get(UUID(str(session_id)))

    def list(self, limit: int = 50) -> list[PracticeSessionView]:
        rows = (
            self._connection.execute(
                text(
                    f"""
                    {self._view_select()}
                    ORDER BY ps.updated_at DESC
                    LIMIT :limit
                    """
                ),
                {"limit": limit},
            )
            .mappings()
            .all()
        )
        return [self._view(dict(row)) for row in rows]

    def get(self, session_id: UUID) -> PracticeSessionView:
        row = (
            self._connection.execute(
                text(f"{self._view_select()} WHERE ps.id=:session_id"),
                {"session_id": session_id},
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            raise PracticeSessionNotFoundError
        return self._view(dict(row))

    def patch(
        self,
        session_id: UUID,
        update: PracticeSessionPatch,
    ) -> PracticeSessionView:
        current = self.get(session_id)
        if current.state not in {
            PracticeSessionState.created,
            PracticeSessionState.in_progress,
            PracticeSessionState.paused,
        }:
            raise PracticeStateTransitionError("Completed practice sessions are immutable.")
        fields = update.model_fields_set
        self._connection.execute(
            text(
                """
                UPDATE practice_sessions
                SET draft_code=CASE WHEN :set_draft THEN :draft_code ELSE draft_code END,
                    notes=CASE WHEN :set_notes THEN :notes ELSE notes END,
                    elapsed_seconds=CASE
                        WHEN :set_elapsed THEN :elapsed_seconds
                        ELSE elapsed_seconds
                    END,
                    last_activity_at=CURRENT_TIMESTAMP,
                    updated_at=CURRENT_TIMESTAMP
                WHERE id=:session_id
                """
            ),
            {
                "session_id": session_id,
                "set_draft": "draft_code" in fields,
                "draft_code": update.draft_code,
                "set_notes": "notes" in fields,
                "notes": update.notes,
                "set_elapsed": "elapsed_seconds" in fields,
                "elapsed_seconds": update.elapsed_seconds,
            },
        )
        return self.get(session_id)

    def transition(
        self,
        session_id: UUID,
        target: PracticeSessionState,
        allowed: set[PracticeSessionState],
    ) -> PracticeSessionView:
        current = self.get(session_id)
        if current.state not in allowed:
            raise PracticeStateTransitionError(
                f"Cannot transition a {current.state.value} session to {target.value}."
            )
        timestamps = {
            PracticeSessionState.in_progress: "started_at=COALESCE(started_at, CURRENT_TIMESTAMP),",
            PracticeSessionState.paused: "paused_at=CURRENT_TIMESTAMP,",
            PracticeSessionState.submitted: "submitted_at=CURRENT_TIMESTAMP,",
            PracticeSessionState.completed: "completed_at=CURRENT_TIMESTAMP,",
        }
        timestamp_sql = timestamps.get(target, "")
        self._connection.execute(
            text(
                f"""
                UPDATE practice_sessions
                SET state=CAST(:target AS practice_session_state),
                    {timestamp_sql}
                    last_activity_at=CURRENT_TIMESTAMP,
                    updated_at=CURRENT_TIMESTAMP
                WHERE id=:session_id
                """
            ),
            {"session_id": session_id, "target": target.value},
        )
        self.append_event(
            session_id,
            PracticeSessionEventInput(
                event_type=f"SESSION_{target.value}",
                payload={"from": current.state.value, "to": target.value},
            ),
        )
        return self.get(session_id)

    def append_event(
        self,
        session_id: UUID,
        event: PracticeSessionEventInput,
    ) -> None:
        self.get(session_id)
        self._connection.execute(
            text(
                """
                INSERT INTO practice_session_events (
                    session_id, sequence_number, event_type, payload
                )
                SELECT :session_id,
                       COALESCE(max(sequence_number), 0) + 1,
                       :event_type,
                       CAST(:payload AS jsonb)
                FROM practice_session_events
                WHERE session_id=:session_id
                """
            ),
            {
                "session_id": session_id,
                "event_type": event.event_type,
                "payload": json.dumps(event.payload),
            },
        )

    def next_hint(self, session_id: UUID) -> PracticeHint:
        session = self.get(session_id)
        question = published_question_payload(self._connection, session.question_slug)
        hints = question_hints(question)
        if session.hint_count >= len(hints):
            raise PracticeStateTransitionError("No additional hints are available.")
        hint = hints[session.hint_count]
        new_count = session.hint_count + 1
        self._connection.execute(
            text(
                """
                UPDATE practice_sessions
                SET hint_count=:hint_count,
                    last_activity_at=CURRENT_TIMESTAMP,
                    updated_at=CURRENT_TIMESTAMP
                WHERE id=:session_id
                """
            ),
            {"session_id": session_id, "hint_count": new_count},
        )
        self.append_event(
            session_id,
            PracticeSessionEventInput(
                event_type="HINT_REVEALED",
                payload={"reveal_level": int(hint.get("reveal_level", new_count))},
            ),
        )
        return PracticeHint(
            session_id=session_id,
            reveal_level=int(hint.get("reveal_level", new_count)),
            text=str(hint.get("text", "")),
            hint_count=new_count,
        )

    @staticmethod
    def _view_select() -> str:
        return """
            SELECT ps.id, ps.question_version_id, q.slug AS question_slug,
                   v.title AS question_title, v.version AS publication_version,
                   ps.state, ps.runtime, COALESCE(ps.draft_code, '') AS draft_code,
                   COALESCE(ps.notes, '') AS notes, ps.elapsed_seconds,
                   ps.hint_count, ps.run_count, ps.submission_count,
                   ps.started_at, ps.last_activity_at, ps.submitted_at,
                   ps.completed_at, ps.created_at, ps.updated_at
            FROM practice_sessions ps
            JOIN question_versions v ON v.id=ps.question_version_id
            JOIN questions q ON q.id=v.question_id
        """

    @staticmethod
    def _view(row: dict[str, Any]) -> PracticeSessionView:
        return PracticeSessionView.model_validate(row)


def _session_error(exc: Exception) -> HTTPException:
    if isinstance(exc, PracticeSessionNotFoundError):
        return HTTPException(status_code=404, detail="Practice session or question not found.")
    return HTTPException(status_code=409, detail=str(exc))


CandidateWritePrincipal = Annotated[
    AuthenticatedPrincipal,
    Depends(require_permissions("submission:create")),
]
CandidateReadPrincipal = Annotated[
    AuthenticatedPrincipal,
    Depends(require_permissions("submission:read-own")),
]


@router.post("/practice-sessions", response_model=PracticeSessionView, status_code=201)
def create_practice_session(
    request: PracticeSessionCreateRequest,
    principal: CandidateWritePrincipal,
    engine: DatabaseEngine,
) -> PracticeSessionView:
    try:
        with principal_transaction(engine, principal) as connection:
            return PracticeSessionRepository(connection).create(principal, request)
    except (PracticeSessionNotFoundError, PracticeStateTransitionError) as exc:
        raise _session_error(exc) from exc


@router.get("/practice-sessions", response_model=list[PracticeSessionView])
def list_practice_sessions(
    principal: CandidateReadPrincipal,
    engine: DatabaseEngine,
) -> list[PracticeSessionView]:
    with principal_transaction(engine, principal) as connection:
        return PracticeSessionRepository(connection).list()


@router.get("/practice-sessions/{session_id}", response_model=PracticeSessionView)
def get_practice_session(
    session_id: UUID,
    principal: CandidateReadPrincipal,
    engine: DatabaseEngine,
) -> PracticeSessionView:
    try:
        with principal_transaction(engine, principal) as connection:
            return PracticeSessionRepository(connection).get(session_id)
    except PracticeSessionNotFoundError as exc:
        raise _session_error(exc) from exc


@router.patch("/practice-sessions/{session_id}", response_model=PracticeSessionView)
def patch_practice_session(
    session_id: UUID,
    update: PracticeSessionPatch,
    principal: CandidateWritePrincipal,
    engine: DatabaseEngine,
) -> PracticeSessionView:
    try:
        with principal_transaction(engine, principal) as connection:
            return PracticeSessionRepository(connection).patch(session_id, update)
    except (PracticeSessionNotFoundError, PracticeStateTransitionError) as exc:
        raise _session_error(exc) from exc


def _transition_route(
    session_id: UUID,
    principal: AuthenticatedPrincipal,
    engine: DatabaseEngine,
    target: PracticeSessionState,
    allowed: set[PracticeSessionState],
) -> PracticeSessionView:
    try:
        with principal_transaction(engine, principal) as connection:
            return PracticeSessionRepository(connection).transition(
                session_id,
                target,
                allowed,
            )
    except (PracticeSessionNotFoundError, PracticeStateTransitionError) as exc:
        raise _session_error(exc) from exc


@router.post("/practice-sessions/{session_id}/start", response_model=PracticeSessionView)
def start_practice_session(
    session_id: UUID,
    principal: CandidateWritePrincipal,
    engine: DatabaseEngine,
) -> PracticeSessionView:
    return _transition_route(
        session_id,
        principal,
        engine,
        PracticeSessionState.in_progress,
        {PracticeSessionState.created},
    )


@router.post("/practice-sessions/{session_id}/pause", response_model=PracticeSessionView)
def pause_practice_session(
    session_id: UUID,
    principal: CandidateWritePrincipal,
    engine: DatabaseEngine,
) -> PracticeSessionView:
    return _transition_route(
        session_id,
        principal,
        engine,
        PracticeSessionState.paused,
        {PracticeSessionState.in_progress},
    )


@router.post("/practice-sessions/{session_id}/resume", response_model=PracticeSessionView)
def resume_practice_session(
    session_id: UUID,
    principal: CandidateWritePrincipal,
    engine: DatabaseEngine,
) -> PracticeSessionView:
    return _transition_route(
        session_id,
        principal,
        engine,
        PracticeSessionState.in_progress,
        {PracticeSessionState.paused},
    )


@router.post("/practice-sessions/{session_id}/events", status_code=204)
def append_practice_event(
    session_id: UUID,
    event: PracticeSessionEventInput,
    principal: CandidateWritePrincipal,
    engine: DatabaseEngine,
) -> None:
    try:
        with principal_transaction(engine, principal) as connection:
            PracticeSessionRepository(connection).append_event(session_id, event)
    except PracticeSessionNotFoundError as exc:
        raise _session_error(exc) from exc


@router.post("/practice-sessions/{session_id}/complete", response_model=PracticeSessionView)
def complete_practice_session(
    session_id: UUID,
    principal: CandidateWritePrincipal,
    engine: DatabaseEngine,
) -> PracticeSessionView:
    return _transition_route(
        session_id,
        principal,
        engine,
        PracticeSessionState.completed,
        {PracticeSessionState.submitted, PracticeSessionState.evaluating},
    )


@router.post("/practice-sessions/{session_id}/hints", response_model=PracticeHint)
def reveal_practice_hint(
    session_id: UUID,
    principal: CandidateWritePrincipal,
    engine: DatabaseEngine,
) -> PracticeHint:
    try:
        with principal_transaction(engine, principal) as connection:
            return PracticeSessionRepository(connection).next_hint(session_id)
    except (PracticeSessionNotFoundError, PracticeStateTransitionError) as exc:
        raise _session_error(exc) from exc
