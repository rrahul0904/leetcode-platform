"""Private, immutable-version-bound test fixture staging for employer code questions.

This module never executes candidate code. Fixtures remain in privileged RLS
storage. The trusted sandbox controller must be integrated and certified before
enabling objective employer coding scores or candidate Run/Submit.
"""

from __future__ import annotations

import hashlib
import json
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import text

from .auth import authenticated_principal
from .database import DatabaseEngine, principal_transaction
from .employer_assessment_routes import _ORG, _USER, _member, _org_assessment
from .persistence import audit_event
from .schemas import AuthenticatedPrincipal

router = APIRouter(prefix="/api/v1", tags=["employer-private-code-fixtures"])
Principal = Annotated[AuthenticatedPrincipal, Depends(authenticated_principal)]


class PrivateCodeCase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: str = Field(pattern=r"^[a-z][a-z0-9_-]{2,49}$")
    visibility: Literal["sample", "hidden"]
    input_data: str = Field(max_length=20_000)
    expected_output: str = Field(max_length=20_000)
    points: int = Field(ge=0, le=100)


class PrivateCodeBundle(BaseModel):
    model_config = ConfigDict(extra="forbid")

    language: Literal["python", "sql"]
    cases: list[PrivateCodeCase] = Field(min_length=2, max_length=30)

    @model_validator(mode="after")
    def check_cases(self) -> PrivateCodeBundle:
        names = [case.case_id for case in self.cases]
        if len(names) != len(set(names)):
            raise ValueError("Test case identifiers must be unique")
        samples = [case for case in self.cases if case.visibility == "sample"]
        hidden = [case for case in self.cases if case.visibility == "hidden"]
        if not samples or not hidden:
            raise ValueError("Both sample and hidden test cases are required")
        if any(case.points != 0 for case in samples):
            raise ValueError("Public sample test cases must have zero marks")
        if any(case.points < 1 for case in hidden):
            raise ValueError("Confidential hidden cases must have positive marks")
        return self


class PrivateCodeBundleReceipt(BaseModel):
    model_config = ConfigDict(extra="forbid")

    assessment_version_id: UUID
    source_sha256: str
    question_number: int
    language: Literal["python", "sql"]
    bundle_sha256: str
    sample_count: int
    hidden_count: int


@router.put(
    "/employer/assessments/{assessment_id}/code-test-bundles/{question_number}",
    response_model=PrivateCodeBundleReceipt,
)
def stage_employer_code_bundle(
    assessment_id: UUID,
    question_number: int,
    payload: PrivateCodeBundle,
    engine: DatabaseEngine,
    principal: Principal,
) -> PrivateCodeBundleReceipt:
    """Stage private fixture metadata; NEVER execute candidate code in this route."""
    with principal_transaction(engine, principal) as conn:
        _member(conn, principal, ("owner", "admin"))
        assessment = _org_assessment(conn, assessment_id, lock=True)
        if assessment["status"] != "review_required":
            raise HTTPException(status_code=409, detail="Published assessment fixtures are immutable")
        questions = assessment["candidate_blueprint"]["questions"]
        question = next((q for q in questions if int(q["number"]) == question_number), None)
        if question is None or question["kind"] != "code":
            raise HTTPException(status_code=422, detail="Fixture target must be a coding question")
        if question.get("language") != payload.language:
            raise HTTPException(status_code=422, detail="Fixture runtime must equal published language")
        if sum(case.points for case in payload.cases) != int(question["marks"]):
            raise HTTPException(status_code=422, detail="Hidden case points must equal question marks")

        existing = conn.execute(
            text(
                f"""SELECT source_sha256
                    FROM employer_assessment_private_keys
                    WHERE assessment_version_id=:assessment AND organization_id={_ORG}
                    FOR UPDATE"""
            ),
            {"assessment": assessment_id},
        ).scalar_one_or_none()
        if existing is None or existing != assessment["content_sha256"]:
            raise HTTPException(
                status_code=409,
                detail="First establish a matching confidential assessment rubric",
            )

        canonical = json.dumps(
            payload.model_dump(), sort_keys=True, separators=(",", ":"),
        )
        digest = hashlib.sha256(canonical.encode()).hexdigest()
        entry = json.dumps(
            {str(question_number): {"source_sha256": assessment["content_sha256"],
                                    "bundle_sha256": digest,
                                    "bundle": payload.model_dump()}},
            sort_keys=True, separators=(",", ":"),
        )
        conn.execute(
            text(
                f"""UPDATE employer_assessment_private_keys
                    SET private_rubric=jsonb_set(
                        private_rubric, '{{code_test_bundles}}',
                        COALESCE(private_rubric->'code_test_bundles', '{{}}'::jsonb)
                        || CAST(:entry AS jsonb), true)
                    WHERE assessment_version_id=:assessment
                      AND organization_id={_ORG}
                      AND source_sha256=:source_sha256"""
            ),
            {
                "entry": entry,
                "assessment": assessment_id,
                "source_sha256": assessment["content_sha256"],
            },
        )
        actor = conn.execute(text(f"SELECT {_USER}")).scalar_one()
        audit_event(
            conn, principal, actor, action="assessment.code_fixture_stage",
            resource_type="employer_assessment", resource_id=str(assessment_id),
            details={"question_number": question_number, "bundle_sha256": digest,
                     "case_count": len(payload.cases)},
        )
        return PrivateCodeBundleReceipt(
            assessment_version_id=assessment_id,
            source_sha256=assessment["content_sha256"],
            question_number=question_number,
            language=payload.language,
            bundle_sha256=digest,
            sample_count=sum(c.visibility == "sample" for c in payload.cases),
            hidden_count=sum(c.visibility == "hidden" for c in payload.cases),
        )
