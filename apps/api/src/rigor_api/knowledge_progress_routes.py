from __future__ import annotations

import json
from datetime import date, timedelta
from typing import Annotated, Literal, cast
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text

from .auth import require_permissions
from .database import DatabaseEngine, principal_transaction
from .schemas import AuthenticatedPrincipal

router = APIRouter(prefix="/knowledge/me", tags=["knowledge-progress"])


class ProgressModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CandidateProblemState(ProgressModel):
    problem_id: UUID
    slug: str
    title: str
    status: Literal["viewed", "attempted", "solved", "failed"]
    bookmarked: bool
    revision_status: Literal["none", "marked", "due", "completed"]
    private_notes: str
    view_count: int = Field(ge=0)
    attempt_count: int = Field(ge=0)
    solved_count: int = Field(ge=0)
    failed_count: int = Field(ge=0)
    total_seconds: int = Field(ge=0)
    last_language: str | None
    first_viewed_at: str | None
    last_attempted_at: str | None
    solved_at: str | None
    last_activity_at: str


class CandidateProblemPatch(ProgressModel):
    bookmarked: bool | None = None
    revision_status: Literal["none", "marked", "due", "completed"] | None = None
    private_notes: str | None = Field(default=None, max_length=50_000)


class ActivityInput(ProgressModel):
    event_type: Literal[
        "problem_viewed",
        "session_started",
        "draft_saved",
        "public_tests_run",
        "submission_completed",
        "problem_solved",
        "problem_failed",
        "session_time_recorded",
    ]
    language: str | None = Field(default=None, max_length=50)
    duration_seconds: int = Field(default=0, ge=0, le=86_400)
    idempotency_key: str | None = Field(default=None, min_length=8, max_length=180)
    payload: dict[str, object] = Field(default_factory=dict)


class ProgressSummary(ProgressModel):
    viewed: int
    attempted: int
    solved: int
    failed: int
    bookmarked: int
    revision_due: int
    total_seconds: int
    current_streak: int
    longest_streak: int
    languages: dict[str, int]


CandidateReadPrincipal = Annotated[
    AuthenticatedPrincipal,
    Depends(require_permissions("submission:read-own")),
]
CandidateWritePrincipal = Annotated[
    AuthenticatedPrincipal,
    Depends(require_permissions("submission:create")),
]


def _candidate_id(connection) -> UUID:
    value = connection.execute(
        text("SELECT NULLIF(current_setting('rigor.user_id', true), '')::uuid")
    ).scalar_one()
    if value is None:
        raise HTTPException(status_code=401, detail="Candidate context is unavailable")
    return UUID(str(value))


def _problem_id(connection, slug: str) -> UUID:
    value = connection.execute(
        text(
            """
            SELECT id
            FROM knowledge_problems
            WHERE slug=:slug AND deleted_at IS NULL
              AND publication_status IN ('published', 'metadata_only')
            """
        ),
        {"slug": slug},
    ).scalar_one_or_none()
    if value is None:
        raise HTTPException(status_code=404, detail="Knowledge-bank problem not found")
    return UUID(str(value))


def _ensure_state(connection, candidate_id: UUID, problem_id: UUID) -> None:
    connection.execute(
        text(
            """
            INSERT INTO knowledge_candidate_problem_state (
                candidate_id, problem_id, status, first_viewed_at, view_count
            ) VALUES (
                :candidate_id, :problem_id, 'viewed', CURRENT_TIMESTAMP, 0
            )
            ON CONFLICT (candidate_id, problem_id) DO NOTHING
            """
        ),
        {"candidate_id": candidate_id, "problem_id": problem_id},
    )


def _state(connection, candidate_id: UUID, problem_id: UUID) -> CandidateProblemState:
    row = (
        connection.execute(
            text(
                """
            SELECT state.problem_id, problem.slug, problem.title,
                   state.status, state.bookmarked, state.revision_status,
                   state.private_notes, state.view_count, state.attempt_count,
                   state.solved_count, state.failed_count, state.total_seconds,
                   state.last_language,
                   state.first_viewed_at::text AS first_viewed_at,
                   state.last_attempted_at::text AS last_attempted_at,
                   state.solved_at::text AS solved_at,
                   state.last_activity_at::text AS last_activity_at
            FROM knowledge_candidate_problem_state state
            JOIN knowledge_problems problem ON problem.id=state.problem_id
            WHERE state.candidate_id=:candidate_id AND state.problem_id=:problem_id
            """
            ),
            {"candidate_id": candidate_id, "problem_id": problem_id},
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Candidate problem state not found")
    return CandidateProblemState.model_validate(dict(row))


def _append_event(
    connection,
    *,
    candidate_id: UUID,
    problem_id: UUID,
    event_type: str,
    language: str | None,
    duration_seconds: int,
    idempotency_key: str | None,
    payload: dict[str, object],
) -> bool:
    inserted = connection.execute(
        text(
            """
            INSERT INTO knowledge_activity_events (
                candidate_id, problem_id, event_type, language,
                duration_seconds, payload, idempotency_key
            ) VALUES (
                :candidate_id, :problem_id, :event_type, :language,
                :duration_seconds, CAST(:payload AS jsonb), :idempotency_key
            )
            ON CONFLICT (candidate_id, idempotency_key)
            WHERE idempotency_key IS NOT NULL
            DO NOTHING
            RETURNING id
            """
        ),
        {
            "candidate_id": candidate_id,
            "problem_id": problem_id,
            "event_type": event_type,
            "language": language,
            "duration_seconds": duration_seconds,
            "payload": json.dumps(payload),
            "idempotency_key": idempotency_key,
        },
    ).scalar_one_or_none()
    return inserted is not None


def _apply_event_projection(
    connection,
    *,
    candidate_id: UUID,
    problem_id: UUID,
    event: ActivityInput,
) -> None:
    attempted = event.event_type in {
        "session_started",
        "draft_saved",
        "public_tests_run",
        "submission_completed",
        "problem_failed",
    }
    viewed_increment = 1 if event.event_type == "problem_viewed" else 0
    attempted_increment = (
        1 if event.event_type in {"public_tests_run", "submission_completed"} else 0
    )
    solved_increment = 1 if event.event_type == "problem_solved" else 0
    failed_increment = 1 if event.event_type == "problem_failed" else 0
    connection.execute(
        text(
            """
            UPDATE knowledge_candidate_problem_state
            SET status=CASE
                  WHEN :solved THEN 'solved'
                  WHEN status='solved' THEN status
                  WHEN :failed THEN 'failed'
                  WHEN :attempted THEN 'attempted'
                  ELSE status
                END,
                view_count=view_count + :viewed_increment,
                attempt_count=attempt_count + :attempted_increment,
                solved_count=solved_count + :solved_increment,
                failed_count=failed_count + :failed_increment,
                total_seconds=total_seconds + :duration_seconds,
                last_language=COALESCE(:language, last_language),
                first_viewed_at=COALESCE(first_viewed_at, CURRENT_TIMESTAMP),
                last_attempted_at=CASE
                  WHEN :attempted OR :solved OR :failed THEN CURRENT_TIMESTAMP
                  ELSE last_attempted_at
                END,
                solved_at=CASE WHEN :solved THEN CURRENT_TIMESTAMP ELSE solved_at END,
                last_activity_at=CURRENT_TIMESTAMP,
                updated_at=CURRENT_TIMESTAMP
            WHERE candidate_id=:candidate_id AND problem_id=:problem_id
            """
        ),
        {
            "candidate_id": candidate_id,
            "problem_id": problem_id,
            "solved": event.event_type == "problem_solved",
            "failed": event.event_type == "problem_failed",
            "attempted": attempted,
            "viewed_increment": viewed_increment,
            "attempted_increment": attempted_increment,
            "solved_increment": solved_increment,
            "failed_increment": failed_increment,
            "duration_seconds": event.duration_seconds,
            "language": event.language,
        },
    )


def _streaks(days: list[date]) -> tuple[int, int]:
    if not days:
        return 0, 0
    ordered = sorted(set(days), reverse=True)
    longest = 1
    running = 1
    for previous, current in zip(ordered, ordered[1:], strict=False):
        if previous - current == timedelta(days=1):
            running += 1
            longest = max(longest, running)
        else:
            running = 1
    today = date.today()
    if ordered[0] not in {today, today - timedelta(days=1)}:
        return 0, longest
    current_streak = 1
    for previous, current in zip(ordered, ordered[1:], strict=False):
        if previous - current != timedelta(days=1):
            break
        current_streak += 1
    return current_streak, longest


@router.get("/problems/{slug}", response_model=CandidateProblemState)
def get_candidate_problem_state(
    slug: str,
    principal: CandidateReadPrincipal,
    engine: DatabaseEngine,
) -> CandidateProblemState:
    with principal_transaction(engine, principal) as connection:
        candidate_id = _candidate_id(connection)
        problem_id = _problem_id(connection, slug)
        _ensure_state(connection, candidate_id, problem_id)
        return _state(connection, candidate_id, problem_id)


@router.patch("/problems/{slug}", response_model=CandidateProblemState)
def patch_candidate_problem_state(
    slug: str,
    update: CandidateProblemPatch,
    principal: CandidateWritePrincipal,
    engine: DatabaseEngine,
) -> CandidateProblemState:
    with principal_transaction(engine, principal) as connection:
        candidate_id = _candidate_id(connection)
        problem_id = _problem_id(connection, slug)
        _ensure_state(connection, candidate_id, problem_id)
        fields = update.model_fields_set
        connection.execute(
            text(
                """
                UPDATE knowledge_candidate_problem_state
                SET bookmarked=CASE WHEN :set_bookmarked THEN :bookmarked ELSE bookmarked END,
                    revision_status=CASE
                      WHEN :set_revision THEN :revision_status
                      ELSE revision_status
                    END,
                    private_notes=CASE WHEN :set_notes THEN :private_notes ELSE private_notes END,
                    last_activity_at=CURRENT_TIMESTAMP,
                    updated_at=CURRENT_TIMESTAMP
                WHERE candidate_id=:candidate_id AND problem_id=:problem_id
                """
            ),
            {
                "candidate_id": candidate_id,
                "problem_id": problem_id,
                "set_bookmarked": "bookmarked" in fields,
                "bookmarked": update.bookmarked,
                "set_revision": "revision_status" in fields,
                "revision_status": update.revision_status,
                "set_notes": "private_notes" in fields,
                "private_notes": update.private_notes,
            },
        )
        if "bookmarked" in fields:
            _append_event(
                connection,
                candidate_id=candidate_id,
                problem_id=problem_id,
                event_type="bookmark_changed",
                language=None,
                duration_seconds=0,
                idempotency_key=None,
                payload={"bookmarked": update.bookmarked},
            )
        if "revision_status" in fields:
            _append_event(
                connection,
                candidate_id=candidate_id,
                problem_id=problem_id,
                event_type="revision_changed",
                language=None,
                duration_seconds=0,
                idempotency_key=None,
                payload={"revision_status": update.revision_status},
            )
        if "private_notes" in fields:
            _append_event(
                connection,
                candidate_id=candidate_id,
                problem_id=problem_id,
                event_type="notes_saved",
                language=None,
                duration_seconds=0,
                idempotency_key=None,
                payload={"length": len(update.private_notes or "")},
            )
        return _state(connection, candidate_id, problem_id)


@router.post("/problems/{slug}/events", response_model=CandidateProblemState)
def record_candidate_activity(
    slug: str,
    event: ActivityInput,
    principal: CandidateWritePrincipal,
    engine: DatabaseEngine,
) -> CandidateProblemState:
    with principal_transaction(engine, principal) as connection:
        candidate_id = _candidate_id(connection)
        problem_id = _problem_id(connection, slug)
        _ensure_state(connection, candidate_id, problem_id)
        inserted = _append_event(
            connection,
            candidate_id=candidate_id,
            problem_id=problem_id,
            event_type=event.event_type,
            language=event.language,
            duration_seconds=event.duration_seconds,
            idempotency_key=event.idempotency_key,
            payload=event.payload,
        )
        if inserted:
            _apply_event_projection(
                connection,
                candidate_id=candidate_id,
                problem_id=problem_id,
                event=event,
            )
        return _state(connection, candidate_id, problem_id)


@router.get("/summary", response_model=ProgressSummary)
def candidate_progress_summary(
    principal: CandidateReadPrincipal,
    engine: DatabaseEngine,
) -> ProgressSummary:
    with principal_transaction(engine, principal) as connection:
        candidate_id = _candidate_id(connection)
        row = (
            connection.execute(
                text(
                    """
                SELECT
                  count(*) FILTER (WHERE status='viewed') AS viewed,
                  count(*) FILTER (WHERE status='attempted') AS attempted,
                  count(*) FILTER (WHERE status='solved') AS solved,
                  count(*) FILTER (WHERE status='failed') AS failed,
                  count(*) FILTER (WHERE bookmarked) AS bookmarked,
                  count(*) FILTER (WHERE revision_status IN ('marked', 'due')) AS revision_due,
                  COALESCE(sum(total_seconds), 0) AS total_seconds
                FROM knowledge_candidate_problem_state
                WHERE candidate_id=:candidate_id
                """
                ),
                {"candidate_id": candidate_id},
            )
            .mappings()
            .one()
        )
        day_rows = (
            connection.execute(
                text(
                    """
                SELECT DISTINCT occurred_at::date AS activity_date
                FROM knowledge_activity_events
                WHERE candidate_id=:candidate_id
                ORDER BY activity_date DESC
                """
                ),
                {"candidate_id": candidate_id},
            )
            .scalars()
            .all()
        )
        language_rows = (
            connection.execute(
                text(
                    """
                SELECT language, count(*) AS event_count
                FROM knowledge_activity_events
                WHERE candidate_id=:candidate_id AND language IS NOT NULL
                GROUP BY language
                ORDER BY event_count DESC, language
                """
                ),
                {"candidate_id": candidate_id},
            )
            .mappings()
            .all()
        )
    current_streak, longest_streak = _streaks([cast(date, value) for value in day_rows])
    return ProgressSummary(
        viewed=int(row["viewed"]),
        attempted=int(row["attempted"]),
        solved=int(row["solved"]),
        failed=int(row["failed"]),
        bookmarked=int(row["bookmarked"]),
        revision_due=int(row["revision_due"]),
        total_seconds=int(row["total_seconds"]),
        current_streak=current_streak,
        longest_streak=longest_streak,
        languages={str(item["language"]): int(item["event_count"]) for item in language_rows},
    )


@router.get("/bookmarks", response_model=list[CandidateProblemState])
def candidate_bookmarks(
    principal: CandidateReadPrincipal,
    engine: DatabaseEngine,
) -> list[CandidateProblemState]:
    with principal_transaction(engine, principal) as connection:
        candidate_id = _candidate_id(connection)
        rows = (
            connection.execute(
                text(
                    """
                SELECT state.problem_id, problem.slug, problem.title,
                       state.status, state.bookmarked, state.revision_status,
                       state.private_notes, state.view_count, state.attempt_count,
                       state.solved_count, state.failed_count, state.total_seconds,
                       state.last_language,
                       state.first_viewed_at::text AS first_viewed_at,
                       state.last_attempted_at::text AS last_attempted_at,
                       state.solved_at::text AS solved_at,
                       state.last_activity_at::text AS last_activity_at
                FROM knowledge_candidate_problem_state state
                JOIN knowledge_problems problem ON problem.id=state.problem_id
                WHERE state.candidate_id=:candidate_id AND state.bookmarked
                ORDER BY state.last_activity_at DESC
                """
                ),
                {"candidate_id": candidate_id},
            )
            .mappings()
            .all()
        )
    return [CandidateProblemState.model_validate(dict(row)) for row in rows]


from .practice import router as application_router  # noqa: E402

application_router.include_router(router)
