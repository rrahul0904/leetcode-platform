from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Any, cast
from uuid import UUID

from fastapi import Depends, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import Connection, text

from .auth import require_permissions
from .database import DatabaseEngine, principal_transaction
from .execution_domain import (
    ExecutionNotFoundError,
    ExecutionRepository,
    ExecutionTransitionError,
    ExecutionType,
    IdempotencyConflictError,
    execution_request_hash,
)
from .practice import (
    PracticeSessionNotFoundError,
    PracticeSessionRepository,
    published_question_payload,
    question_mode,
    question_tests,
)
from .sandbox_jobs import sandbox_profile
from .schemas import (
    AuthenticatedPrincipal,
    PracticeRunRequest,
    PracticeSessionEventInput,
    PracticeSessionState,
    PracticeSubmitRequest,
)


class ApiExecutionModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AsyncExecutionStatus(StrEnum):
    queued = "QUEUED"
    dispatching = "DISPATCHING"
    running = "RUNNING"
    completed = "COMPLETED"
    failed = "FAILED"
    timeout = "TIMEOUT"
    cancelled = "CANCELLED"


class ExecutionAccepted(ApiExecutionModel):
    execution_id: UUID
    submission_id: UUID | None
    status: AsyncExecutionStatus
    duplicate: bool = False


class AsyncPublicTestResult(ApiExecutionModel):
    test_id: str
    name: str
    passed: bool
    expected: object | None = None
    actual: object | None = None
    error_category: str | None = None


class AsyncExecutionResult(ApiExecutionModel):
    public_results: list[AsyncPublicTestResult] = []
    hidden_total: int = Field(default=0, ge=0)
    hidden_passed: int = Field(default=0, ge=0)
    stdout: str = ""
    stderr: str = ""
    candidate_message: str | None = None


class AsyncExecutionView(ApiExecutionModel):
    execution_id: UUID
    submission_id: UUID | None
    status: AsyncExecutionStatus
    execution_type: str
    runtime: str
    created_at: datetime
    queued_at: datetime
    dispatch_started_at: datetime | None
    running_at: datetime | None
    completed_at: datetime | None
    runtime_ms: int | None = Field(default=None, ge=0)
    error_category: str | None
    result: AsyncExecutionResult | None = None


CandidateWritePrincipal = Annotated[
    AuthenticatedPrincipal,
    Depends(require_permissions("submission:create")),
]
CandidateReadPrincipal = Annotated[
    AuthenticatedPrincipal,
    Depends(require_permissions("submission:read-own")),
]
IdempotencyHeader = Annotated[
    str,
    Header(alias="Idempotency-Key", min_length=8, max_length=160),
]
QuestionSlugHeader = Annotated[
    str,
    Header(alias="X-Rigor-Question-Slug", min_length=3, max_length=180),
]

MAX_ACTIVE_RUNS_PER_CANDIDATE = 5
MAX_ACTIVE_SUBMITS_PER_CANDIDATE = 2
ACTIVE_STATES = ("QUEUED", "DISPATCHING", "RUNNING")
PYTHON_RUNTIME = "python3.13"


def _session_question(
    connection: Connection,
    *,
    session_id: UUID,
    slug: str,
) -> dict[str, Any]:
    row = (
        connection.execute(
            text(
                """
                SELECT ps.state::text AS state
                FROM practice_sessions ps
                JOIN question_versions v ON v.id=ps.question_version_id
                JOIN questions q ON q.id=v.question_id
                WHERE ps.id=:session_id
                  AND q.slug=:slug
                  AND ps.candidate_id=NULLIF(
                    current_setting('rigor.user_id', true), ''
                  )::uuid
                """
            ),
            {"session_id": session_id, "slug": slug},
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        raise PracticeSessionNotFoundError
    if str(row["state"]) in {"COMPLETED", "ABANDONED"}:
        raise HTTPException(status_code=409, detail="Practice session is no longer executable.")
    return published_question_payload(connection, slug)


def _request_hash(
    *,
    execution_type: ExecutionType,
    session_id: UUID,
    question_version_id: UUID,
    source_code: str,
) -> str:
    return execution_request_hash(
        execution_type=execution_type,
        practice_session_id=session_id,
        question_version_id=question_version_id,
        runtime=PYTHON_RUNTIME,
        source_code=source_code,
    )


def _existing_execution(
    connection: Connection,
    *,
    idempotency_key: str,
    expected_request_hash: str,
) -> ExecutionAccepted | None:
    row = (
        connection.execute(
            text(
                """
                SELECT id, submission_id, state::text AS state, request_hash
                FROM execution_requests
                WHERE candidate_id=NULLIF(
                    current_setting('rigor.user_id', true), ''
                )::uuid
                  AND idempotency_key=:idempotency_key
                """
            ),
            {"idempotency_key": idempotency_key},
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        return None
    if str(row["request_hash"]) != expected_request_hash:
        raise IdempotencyConflictError(
            "The Idempotency-Key was already used for a different execution request."
        )
    return ExecutionAccepted(
        execution_id=UUID(str(row["id"])),
        submission_id=UUID(str(row["submission_id"])) if row["submission_id"] else None,
        status=AsyncExecutionStatus(str(row["state"])),
        duplicate=True,
    )


def _enforce_backpressure(
    connection: Connection,
    *,
    execution_type: ExecutionType,
) -> None:
    maximum = (
        MAX_ACTIVE_RUNS_PER_CANDIDATE
        if execution_type is ExecutionType.run
        else MAX_ACTIVE_SUBMITS_PER_CANDIDATE
    )
    active = int(
        connection.execute(
            text(
                """
                SELECT count(*)
                FROM execution_requests
                WHERE candidate_id=NULLIF(
                    current_setting('rigor.user_id', true), ''
                )::uuid
                  AND execution_type=:execution_type
                  AND state::text = ANY(CAST(:states AS text[]))
                """
            ),
            {
                "execution_type": execution_type.value,
                "states": list(ACTIVE_STATES),
            },
        ).scalar_one()
    )
    if active >= maximum:
        raise HTTPException(
            status_code=429,
            detail="Too many candidate executions are already active. Retry after one finishes.",
        )


def _candidate_tests(
    question: dict[str, Any],
    *,
    public_only: bool,
) -> list[dict[str, object]]:
    sanitized: list[dict[str, object]] = []
    for index, test in enumerate(question_tests(question, public_only=public_only)):
        sanitized.append(
            {
                "id": str(test.get("id") or f"test-{index + 1}"),
                "visibility": str(test.get("visibility") or "hidden"),
                "input": cast(object, test.get("input")),
            }
        )
    if not sanitized:
        raise HTTPException(status_code=409, detail="Question has no executable tests.")
    return sanitized


def _entrypoint(question: dict[str, Any]) -> str:
    mode = question_mode(question)
    value = mode.get("entrypoint") or mode.get("function_name") or "solve"
    entrypoint = str(value)
    if not entrypoint.isidentifier():
        raise HTTPException(status_code=409, detail="Question execution entrypoint is invalid.")
    return entrypoint


def _limits(profile_name: str) -> dict[str, object]:
    profile = sandbox_profile(profile_name)
    return {
        "profile": profile.name,
        "cpu_limit": profile.cpu_limit,
        "memory_limit": profile.memory_limit,
        "ephemeral_storage_limit": profile.ephemeral_storage_limit,
        "execution_timeout_seconds": profile.execution_timeout_seconds,
        "job_deadline_seconds": profile.job_deadline_seconds,
    }


def _queue_execution(
    connection: Connection,
    principal: AuthenticatedPrincipal,
    *,
    execution_type: ExecutionType,
    session_id: UUID,
    question: dict[str, Any],
    source_code: str,
    idempotency_key: str,
    submission_id: UUID | None,
) -> ExecutionAccepted:
    _enforce_backpressure(connection, execution_type=execution_type)
    queued = ExecutionRepository(connection).create_queued(
        execution_type=execution_type,
        practice_session_id=session_id,
        submission_id=submission_id,
        question_version_id=UUID(str(question["question_version_id"])),
        runtime=PYTHON_RUNTIME,
        language="python",
        source_code=source_code,
        idempotency_key=idempotency_key,
        trace_id=principal.correlation_id,
        limits=_limits("python-small"),
        input_payload={
            "schema_version": 1,
            "entrypoint": _entrypoint(question),
            "tests": _candidate_tests(
                question,
                public_only=execution_type is ExecutionType.run,
            ),
        },
    )
    return ExecutionAccepted(
        execution_id=queued.execution_id,
        submission_id=queued.submission_id,
        status=AsyncExecutionStatus(queued.status.value),
        duplicate=queued.duplicate,
    )


def _public_result(
    connection: Connection,
    execution_id: UUID,
) -> AsyncExecutionResult | None:
    row = (
        connection.execute(
            text(
                """
                SELECT public_results, hidden_total, hidden_passed,
                       stdout, stderr, candidate_message
                FROM execution_public_results
                WHERE execution_request_id=:execution_id
                """
            ),
            {"execution_id": execution_id},
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        return None

    raw_value: object = row["public_results"]
    raw_results = cast(list[object], raw_value) if isinstance(raw_value, list) else []
    parsed_results: list[AsyncPublicTestResult] = []
    for item in raw_results:
        if isinstance(item, dict):
            parsed_results.append(
                AsyncPublicTestResult.model_validate(cast(dict[str, object], item))
            )

    return AsyncExecutionResult(
        public_results=parsed_results,
        hidden_total=int(row["hidden_total"]),
        hidden_passed=int(row["hidden_passed"]),
        stdout=str(row["stdout"] or ""),
        stderr=str(row["stderr"] or ""),
        candidate_message=str(row["candidate_message"]) if row["candidate_message"] else None,
    )


def _view(connection: Connection, execution_id: UUID) -> AsyncExecutionView:
    try:
        snapshot = ExecutionRepository(connection).get(execution_id)
    except ExecutionNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Execution not found.") from exc
    return AsyncExecutionView(
        execution_id=snapshot.execution_id,
        submission_id=snapshot.submission_id,
        status=AsyncExecutionStatus(snapshot.status.value),
        execution_type=snapshot.execution_type.value,
        runtime=snapshot.runtime,
        created_at=snapshot.created_at,
        queued_at=snapshot.queued_at,
        dispatch_started_at=snapshot.dispatch_started_at,
        running_at=snapshot.running_at,
        completed_at=snapshot.completed_at,
        runtime_ms=snapshot.runtime_ms,
        error_category=snapshot.error_category,
        result=_public_result(connection, execution_id),
    )


def _practice_not_found(exc: PracticeSessionNotFoundError) -> HTTPException:
    del exc
    return HTTPException(status_code=404, detail="Practice session or question not found.")


def queue_run(
    request: PracticeRunRequest,
    principal: CandidateWritePrincipal,
    engine: DatabaseEngine,
    idempotency_key: IdempotencyHeader,
    slug: QuestionSlugHeader,
) -> ExecutionAccepted:
    execution_key = f"run:{idempotency_key}"
    try:
        with principal_transaction(engine, principal) as connection:
            question = _session_question(connection, session_id=request.session_id, slug=slug)
            question_version_id = UUID(str(question["question_version_id"]))
            existing = _existing_execution(
                connection,
                idempotency_key=execution_key,
                expected_request_hash=_request_hash(
                    execution_type=ExecutionType.run,
                    session_id=request.session_id,
                    question_version_id=question_version_id,
                    source_code=request.source_code,
                ),
            )
            if existing is not None:
                return existing
            accepted = _queue_execution(
                connection,
                principal,
                execution_type=ExecutionType.run,
                session_id=request.session_id,
                question=question,
                source_code=request.source_code,
                idempotency_key=execution_key,
                submission_id=None,
            )
            connection.execute(
                text(
                    """
                    UPDATE practice_sessions
                    SET draft_code=:source,
                        run_count=run_count + 1,
                        last_activity_at=CURRENT_TIMESTAMP,
                        updated_at=CURRENT_TIMESTAMP
                    WHERE id=:session_id
                    """
                ),
                {"source": request.source_code, "session_id": request.session_id},
            )
            PracticeSessionRepository(connection).append_event(
                request.session_id,
                PracticeSessionEventInput(
                    event_type="CODE_RUN_QUEUED",
                    payload={"execution_id": str(accepted.execution_id)},
                ),
            )
            return accepted
    except PracticeSessionNotFoundError as exc:
        raise _practice_not_found(exc) from exc
    except IdempotencyConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


def queue_submit(
    request: PracticeSubmitRequest,
    principal: CandidateWritePrincipal,
    engine: DatabaseEngine,
    idempotency_key: IdempotencyHeader,
    slug: QuestionSlugHeader,
) -> ExecutionAccepted:
    execution_key = f"submit:{idempotency_key}"
    try:
        with principal_transaction(engine, principal) as connection:
            question = _session_question(connection, session_id=request.session_id, slug=slug)
            question_version_id = UUID(str(question["question_version_id"]))
            existing = _existing_execution(
                connection,
                idempotency_key=execution_key,
                expected_request_hash=_request_hash(
                    execution_type=ExecutionType.submit,
                    session_id=request.session_id,
                    question_version_id=question_version_id,
                    source_code=request.source_code,
                ),
            )
            if existing is not None:
                return existing

            _enforce_backpressure(connection, execution_type=ExecutionType.submit)
            submission_id = UUID(
                str(
                    connection.execute(
                        text(
                            """
                            INSERT INTO submissions (
                                organization_id, candidate_id, practice_session_id,
                                question_version_id, runtime, submitted_source,
                                status, idempotency_key
                            ) VALUES (
                                CAST(NULLIF(:organization_id, '') AS uuid),
                                NULLIF(current_setting('rigor.user_id', true), '')::uuid,
                                :session_id, :question_version_id, :runtime,
                                :source, 'queued', :idempotency_key
                            )
                            RETURNING id
                            """
                        ),
                        {
                            "organization_id": principal.organization_id or "",
                            "session_id": request.session_id,
                            "question_version_id": question_version_id,
                            "runtime": request.runtime.value,
                            "source": request.source_code,
                            "idempotency_key": idempotency_key,
                        },
                    ).scalar_one()
                )
            )
            accepted = _queue_execution(
                connection,
                principal,
                execution_type=ExecutionType.submit,
                session_id=request.session_id,
                question=question,
                source_code=request.source_code,
                idempotency_key=execution_key,
                submission_id=submission_id,
            )
            repository = PracticeSessionRepository(connection)
            repository.transition(
                request.session_id,
                PracticeSessionState.submitted,
                {
                    PracticeSessionState.created,
                    PracticeSessionState.in_progress,
                    PracticeSessionState.paused,
                },
            )
            connection.execute(
                text(
                    """
                    UPDATE practice_sessions
                    SET draft_code=:source,
                        submission_count=submission_count + 1,
                        last_activity_at=CURRENT_TIMESTAMP,
                        updated_at=CURRENT_TIMESTAMP
                    WHERE id=:session_id
                    """
                ),
                {"source": request.source_code, "session_id": request.session_id},
            )
            repository.append_event(
                request.session_id,
                PracticeSessionEventInput(
                    event_type="SUBMISSION_QUEUED",
                    payload={
                        "execution_id": str(accepted.execution_id),
                        "submission_id": str(submission_id),
                    },
                ),
            )
            return accepted
    except PracticeSessionNotFoundError as exc:
        raise _practice_not_found(exc) from exc
    except IdempotencyConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


def get_execution(
    execution_id: UUID,
    principal: CandidateReadPrincipal,
    engine: DatabaseEngine,
) -> AsyncExecutionView:
    with principal_transaction(engine, principal) as connection:
        return _view(connection, execution_id)


def cancel_execution(
    execution_id: UUID,
    principal: CandidateWritePrincipal,
    engine: DatabaseEngine,
) -> AsyncExecutionView:
    try:
        with principal_transaction(engine, principal) as connection:
            ExecutionRepository(connection).cancel(
                execution_id,
                trace_id=principal.correlation_id,
            )
            return _view(connection, execution_id)
    except ExecutionNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Execution not found.") from exc
    except ExecutionTransitionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


# The actual FastAPI routes are mounted on the submissions router by
# execution_legacy_block after the synchronous handlers have been removed.
EXECUTION_ROUTES_REGISTERED = True
