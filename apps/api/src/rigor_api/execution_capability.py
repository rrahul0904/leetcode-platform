from __future__ import annotations

from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from .auth import require_permissions
from .database import DatabaseEngine, principal_transaction
from .execution_api import _entrypoint
from .practice import (
    PracticeSessionNotFoundError,
    PracticeStateTransitionError,
    published_question_payload,
    question_mode,
    question_runtime,
    question_tests,
)
from .schemas import AuthenticatedPrincipal, SubmissionRuntime

router = APIRouter(prefix="/api/v1/questions", tags=["catalog"])


class ExecutionCapability(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question_version_id: UUID
    availability: Literal["runnable", "hosted"]
    runtime: SubmissionRuntime | None = None
    public_test_count: int = Field(ge=0)
    hidden_test_count: int = Field(ge=0)
    reason: str | None = None


def _capability(payload: dict[str, object]) -> ExecutionCapability:
    tests = question_tests(payload, public_only=False)
    public_test_count = sum(test.get("visibility") == "public" for test in tests)
    hidden_test_count = sum(test.get("visibility") == "hidden" for test in tests)
    question_version_id = UUID(str(payload["question_version_id"]))

    try:
        runtime = question_runtime(payload)
    except PracticeStateTransitionError as exc:
        return ExecutionCapability(
            question_version_id=question_version_id,
            availability="hosted",
            public_test_count=public_test_count,
            hidden_test_count=hidden_test_count,
            reason=str(exc),
        )

    if not tests:
        return ExecutionCapability(
            question_version_id=question_version_id,
            availability="hosted",
            runtime=runtime,
            public_test_count=0,
            hidden_test_count=0,
            reason="No deterministic execution tests are published for this question version.",
        )

    mode = question_mode(payload)
    if runtime is SubmissionRuntime.postgresql:
        schema_sql = mode.get("schema_sql")
        if not isinstance(schema_sql, str) or not schema_sql.strip():
            return ExecutionCapability(
                question_version_id=question_version_id,
                availability="hosted",
                runtime=runtime,
                public_test_count=public_test_count,
                hidden_test_count=hidden_test_count,
                reason="The published SQL question does not define an isolated fixture schema.",
            )
    else:
        try:
            _entrypoint(payload)
        except HTTPException as exc:
            return ExecutionCapability(
                question_version_id=question_version_id,
                availability="hosted",
                runtime=runtime,
                public_test_count=public_test_count,
                hidden_test_count=hidden_test_count,
                reason=str(exc.detail),
            )

    return ExecutionCapability(
        question_version_id=question_version_id,
        availability="runnable",
        runtime=runtime,
        public_test_count=public_test_count,
        hidden_test_count=hidden_test_count,
    )


def get_execution_capability(
    slug: str,
    principal: Annotated[
        AuthenticatedPrincipal, Depends(require_permissions("catalog:read"))
    ],
    engine: DatabaseEngine,
) -> ExecutionCapability:
    try:
        with principal_transaction(engine, principal) as connection:
            payload = published_question_payload(connection, slug)
            return _capability(payload)
    except PracticeSessionNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Published question not found") from exc


router.add_api_route(
    "/{slug}/execution-capability",
    get_execution_capability,
    methods=["GET"],
    response_model=ExecutionCapability,
)
