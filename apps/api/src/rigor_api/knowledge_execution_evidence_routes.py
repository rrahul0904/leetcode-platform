from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy import text

from .auth import require_permissions
from .database import DatabaseEngine, principal_transaction
from .execution_domain import ExecutionStatus, ExecutionType, TERMINAL_EXECUTION_STATUSES
from .knowledge_progress_routes import (
    ActivityInput,
    CandidateProblemState,
    _append_event,
    _apply_event_projection,
    _candidate_id,
    _ensure_state,
    _state,
)
from .schemas import AuthenticatedPrincipal

router = APIRouter(prefix="/knowledge/me/execution-evidence", tags=["knowledge-progress"])


class EvidenceModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ExecutionEvidenceSync(EvidenceModel):
    execution_id: UUID
    status: str
    execution_type: str
    inserted_events: list[str]
    state: CandidateProblemState


CandidateWritePrincipal = Annotated[
    AuthenticatedPrincipal,
    Depends(require_permissions("submission:create")),
]


def _execution_evidence(connection, candidate_id: UUID, execution_id: UUID):
    return (
        connection.execute(
            text(
                """
                SELECT er.id,
                       er.execution_type,
                       er.runtime,
                       er.state::text AS status,
                       er.submission_id,
                       er.question_version_id,
                       link.problem_id,
                       COALESCE(jsonb_array_length(result.public_results), 0)
                         AS public_total,
                       COALESCE((
                         SELECT count(*) FILTER (
                           WHERE COALESCE((entry->>'passed')::boolean, false)
                         )
                         FROM jsonb_array_elements(
                           COALESCE(result.public_results, '[]'::jsonb)
                         ) entry
                       ), 0) AS public_passed,
                       COALESCE(result.hidden_total, 0) AS hidden_total,
                       COALESCE(result.hidden_passed, 0) AS hidden_passed
                FROM execution_requests er
                JOIN practice_sessions session
                  ON session.id=er.practice_session_id
                 AND session.candidate_id=:candidate_id
                JOIN knowledge_problem_runtime_links link
                  ON link.question_version_id=er.question_version_id
                 AND link.link_status='verified'
                LEFT JOIN execution_public_results result
                  ON result.execution_request_id=er.id
                WHERE er.id=:execution_id
                  AND er.candidate_id=:candidate_id
                """
            ),
            {"candidate_id": candidate_id, "execution_id": execution_id},
        )
        .mappings()
        .one_or_none()
    )


def _is_passing_submit(row) -> bool:
    if str(row["status"]) != ExecutionStatus.completed.value:
        return False
    public_total = int(row["public_total"])
    hidden_total = int(row["hidden_total"])
    return (
        public_total > 0
        and int(row["public_passed"]) == public_total
        and hidden_total > 0
        and int(row["hidden_passed"]) == hidden_total
    )


def _trusted_event(
    connection,
    *,
    candidate_id: UUID,
    problem_id: UUID,
    execution_id: UUID,
    event_type: str,
    language: str,
    payload: dict[str, object],
) -> bool:
    event = ActivityInput(
        event_type=event_type,
        language=language,
        idempotency_key=f"execution:{execution_id}:{event_type}",
        payload=payload,
    )
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
    return inserted


@router.post("/{execution_id}/sync", response_model=ExecutionEvidenceSync)
def sync_execution_evidence(
    execution_id: UUID,
    principal: CandidateWritePrincipal,
    engine: DatabaseEngine,
) -> ExecutionEvidenceSync:
    """Project immutable learning evidence from a candidate-owned execution.

    The caller can request synchronization but cannot select the event outcome.
    Run/Submit/pass/fail facts are derived only from persisted execution state and
    trusted result aggregates. Repeated calls are idempotent by execution ID.
    """

    with principal_transaction(engine, principal) as connection:
        candidate_id = _candidate_id(connection)
        row = _execution_evidence(connection, candidate_id, execution_id)
        if row is None:
            raise HTTPException(status_code=404, detail="Execution evidence not found")
        try:
            status = ExecutionStatus(str(row["status"]))
            execution_type = ExecutionType(str(row["execution_type"]))
        except ValueError as exc:
            raise HTTPException(status_code=409, detail="Execution state is not supported") from exc
        if status not in TERMINAL_EXECUTION_STATUSES:
            raise HTTPException(status_code=409, detail="Execution is not terminal yet")

        problem_id = UUID(str(row["problem_id"]))
        _ensure_state(connection, candidate_id, problem_id)

        # The 0016 RLS policy permits high-trust event types only inside a
        # transaction that explicitly opts into trusted evidence. This flag is
        # never accepted from an HTTP payload.
        connection.execute(text("SELECT set_config('rigor.trusted_evidence', 'on', true)"))

        base_payload: dict[str, object] = {
            "execution_id": str(execution_id),
            "execution_status": status.value,
            "runtime": str(row["runtime"]),
            "public_total": int(row["public_total"]),
            "public_passed": int(row["public_passed"]),
            "hidden_total": int(row["hidden_total"]),
            "hidden_passed": int(row["hidden_passed"]),
        }
        inserted_events: list[str] = []

        if execution_type is ExecutionType.run:
            if _trusted_event(
                connection,
                candidate_id=candidate_id,
                problem_id=problem_id,
                execution_id=execution_id,
                event_type="public_tests_run",
                language=str(row["runtime"]),
                payload=base_payload,
            ):
                inserted_events.append("public_tests_run")
        else:
            submission_id = row["submission_id"]
            submission_payload = {
                **base_payload,
                "submission_id": str(submission_id) if submission_id is not None else None,
            }
            if _trusted_event(
                connection,
                candidate_id=candidate_id,
                problem_id=problem_id,
                execution_id=execution_id,
                event_type="submission_completed",
                language=str(row["runtime"]),
                payload=submission_payload,
            ):
                inserted_events.append("submission_completed")
            outcome = "problem_solved" if _is_passing_submit(row) else "problem_failed"
            if _trusted_event(
                connection,
                candidate_id=candidate_id,
                problem_id=problem_id,
                execution_id=execution_id,
                event_type=outcome,
                language=str(row["runtime"]),
                payload=submission_payload,
            ):
                inserted_events.append(outcome)

        return ExecutionEvidenceSync(
            execution_id=execution_id,
            status=status.value,
            execution_type=execution_type.value,
            inserted_events=inserted_events,
            state=_state(connection, candidate_id, problem_id),
        )


from .practice import router as application_router  # noqa: E402

application_router.include_router(router)
