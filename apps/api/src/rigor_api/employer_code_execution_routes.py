"""Candidate-owned employer coding execution requests and public result reads.

No source is executed inside FastAPI. Durable outbox events contain only execution
IDs, and the worker loads confidential reference tests under its dedicated role.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Annotated, Any, Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text

from .auth import authenticated_principal
from .database import DatabaseEngine, principal_transaction
from .employer_assessment_routes import (
    _ORG,
    _USER,
    _candidate_attempt,
    _employer_attempt,
    _member,
)
from .schemas import AuthenticatedPrincipal

router = APIRouter(prefix="/api/v1", tags=["employer-candidate-code-executions"])
Principal = Annotated[AuthenticatedPrincipal, Depends(authenticated_principal)]
Idempotency = Annotated[str, Header(alias="Idempotency-Key", min_length=8, max_length=160)]


class CodeExecutionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question_number: int = Field(ge=1, le=100)
    mode: Literal["RUN", "SUBMIT"]


class CodeExecutionView(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: UUID
    attempt_id: UUID
    question_number: int
    language: Literal["python", "sql"]
    execution_mode: Literal["RUN", "SUBMIT"]
    status: str
    created_at: datetime
    runtime_ms: int | None = None
    public_results: list[dict[str, Any]] | None = None
    hidden_total: int | None = None
    hidden_passed: int | None = None
    awarded_marks: int | None = None
    error_category: str | None = None
    duplicate: bool = False


def _view(record: dict[str, Any], *, duplicate: bool = False) -> CodeExecutionView:
    return CodeExecutionView(
        id=record["id"],
        attempt_id=record["attempt_id"],
        question_number=record["question_number"],
        language=record["language"],
        execution_mode=record["execution_mode"],
        status=record["status"],
        created_at=record["created_at"],
        runtime_ms=record["runtime_ms"],
        public_results=record["public_results"],
        hidden_total=record["hidden_total"],
        hidden_passed=record["hidden_passed"],
        awarded_marks=record["awarded_marks"],
        error_category=record["error_category"],
        duplicate=duplicate,
    )


_EXECUTION_COLUMNS = """
    id, attempt_id, question_number, language, execution_mode, status,
    created_at, runtime_ms, public_results, hidden_total, hidden_passed,
    awarded_marks, error_category, request_sha256
"""


@router.post(
    "/assessment-attempts/{attempt_id}/code-executions",
    response_model=CodeExecutionView,
    status_code=202,
)
def queue_employer_code_execution(
    attempt_id: UUID,
    request: CodeExecutionRequest,
    engine: DatabaseEngine,
    principal: Principal,
    idempotency_key: Idempotency,
) -> CodeExecutionView:
    with principal_transaction(engine, principal) as conn:
        attempt = _candidate_attempt(conn, attempt_id, lock=True)
        questions = attempt["candidate_blueprint"]["questions"]
        question = next(
            (q for q in questions if q["number"] == request.question_number), None,
        )
        if question is None or question["kind"] != "code":
            raise HTTPException(status_code=422, detail="Question is not a coding problem")
        language = question.get("language")
        if language not in {"python", "sql"}:
            raise HTTPException(status_code=409, detail="Coding runtime is not approved")
        answer = conn.execute(
            text(
                f"""SELECT answer_text, answer_sha256
                    FROM employer_assessment_responses
                    WHERE attempt_id=:attempt AND question_number=:number
                      AND candidate_id={_USER}"""
            ),
            {"attempt": attempt_id, "number": request.question_number},
        ).mappings().one_or_none()
        if answer is None or not answer["answer_text"].strip():
            raise HTTPException(
                status_code=409, detail="Save a nonempty coding answer before execution",
            )
        source_code = str(answer["answer_text"])
        if len(source_code.encode("utf-8")) > 100_000:
            raise HTTPException(status_code=413, detail="Candidate source is too large")
        source_hash = hashlib.sha256(source_code.encode("utf-8")).hexdigest()
        fingerprint = hashlib.sha256(
            json.dumps(
                {
                    "attempt_id": str(attempt_id),
                    "version_id": str(attempt["assessment_version_id"]),
                    "question_number": request.question_number,
                    "mode": request.mode,
                    "source_sha256": source_hash,
                },
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8"),
        ).hexdigest()

        previous = conn.execute(
            text(
                f"""SELECT {_EXECUTION_COLUMNS}
                    FROM employer_code_executions
                    WHERE candidate_id={_USER} AND idempotency_key=:key"""
            ),
            {"key": idempotency_key},
        ).mappings().one_or_none()
        if previous:
            if previous["request_sha256"] != fingerprint:
                raise HTTPException(
                    status_code=409, detail="Idempotency key already used for another request",
                )
            return _view(dict(previous), duplicate=True)

        now = conn.execute(text("SELECT CURRENT_TIMESTAMP")).scalar_one()
        if request.mode == "RUN":
            if attempt["status"] != "in_progress" or attempt["deadline_at"] <= now:
                raise HTTPException(status_code=409, detail="Coding run window is closed")
        elif attempt["status"] != "submitted":
            raise HTTPException(
                status_code=409,
                detail="Final hidden-test grading requires a submitted assessment",
            )
        if request.mode == "SUBMIT":
            submitted = conn.execute(
                text(
                    f"""SELECT id FROM employer_code_executions
                        WHERE attempt_id=:attempt AND question_number=:number
                          AND execution_mode='SUBMIT'"""
                ),
                {"attempt": attempt_id, "number": request.question_number},
            ).scalar_one_or_none()
            if submitted is not None:
                raise HTTPException(
                    status_code=409, detail="Final coding evaluation already requested",
                )

        execution_id = uuid4()
        inserted = conn.execute(
            text(
                f"""INSERT INTO employer_code_executions
                      (id, organization_id, candidate_id, attempt_id,
                       assessment_version_id, question_number, language,
                       execution_mode, idempotency_key, request_sha256,
                       source_sha256, source_code)
                    SELECT :id, a.organization_id, {_USER}, :attempt, :version,
                           :number, :language, :mode, :key, :request_hash,
                           :source_hash, :source
                    FROM employer_assessment_attempts a
                    WHERE a.id=:attempt AND a.candidate_id={_USER}
                    RETURNING {_EXECUTION_COLUMNS}"""
            ),
            {
                "id": execution_id,
                "attempt": attempt_id,
                "version": attempt["assessment_version_id"],
                "number": request.question_number,
                "language": language,
                "mode": request.mode,
                "key": idempotency_key,
                "request_hash": fingerprint,
                "source_hash": source_hash,
                "source": source_code,
            },
        ).mappings().one()
        conn.execute(
            text(
                """INSERT INTO employer_code_execution_outbox (execution_id)
                   VALUES (:execution)"""
            ),
            {"execution": execution_id},
        )
        return _view(dict(inserted))


@router.get(
    "/assessment-attempts/{attempt_id}/code-executions/{execution_id}",
    response_model=CodeExecutionView,
)
def get_employer_code_execution(
    attempt_id: UUID,
    execution_id: UUID,
    engine: DatabaseEngine,
    principal: Principal,
) -> CodeExecutionView:
    with principal_transaction(engine, principal) as conn:
        _candidate_attempt(conn, attempt_id)
        row = conn.execute(
            text(
                f"""SELECT {_EXECUTION_COLUMNS}
                    FROM employer_code_executions
                    WHERE id=:execution AND attempt_id=:attempt
                      AND candidate_id={_USER}"""
            ),
            {"execution": execution_id, "attempt": attempt_id},
        ).mappings().one_or_none()
        if row is None:
            raise HTTPException(status_code=404, detail="Coding execution not found")
        return _view(dict(row))


@router.get(
    "/employer/attempts/{attempt_id}/code-executions",
    response_model=list[CodeExecutionView],
)
def list_employer_code_execution_results(
    attempt_id: UUID,
    engine: DatabaseEngine,
    principal: Principal,
) -> list[CodeExecutionView]:
    """Review-only test outcomes; hidden case contents never leave privileged storage."""
    with principal_transaction(engine, principal) as conn:
        _member(conn, principal, ("owner", "admin", "reviewer", "interviewer"))
        attempt = _employer_attempt(conn, attempt_id)
        if attempt["status"] != "submitted":
            raise HTTPException(
                status_code=409, detail="Coding results require a submitted assessment",
            )
        rows = conn.execute(
            text(
                f"""SELECT {_EXECUTION_COLUMNS}
                    FROM employer_code_executions
                    WHERE attempt_id=:attempt AND organization_id={_ORG}
                    ORDER BY created_at DESC LIMIT 200"""
            ),
            {"attempt": attempt_id},
        ).mappings().all()
        return [_view(dict(row)) for row in rows]
