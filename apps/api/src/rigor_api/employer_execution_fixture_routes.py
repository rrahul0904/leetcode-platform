"""Private, immutable-version-bound test fixture staging for employer code questions.

This module never executes candidate code. Fixtures remain in privileged RLS
storage. The trusted sandbox controller must be integrated and certified before
enabling objective employer coding scores or candidate Run/Submit.
"""

from __future__ import annotations

import json
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy import text

from .auth import authenticated_principal
from .database import DatabaseEngine, principal_transaction
from .employer_assessment_routes import _ORG, _USER, _member, _org_assessment
from .employer_code_contract import (
    PrivateCodeBundle,
    canonical_bundle_digest,
    verified_code_fixtures,
)
from .persistence import audit_event
from .schemas import AuthenticatedPrincipal

router = APIRouter(prefix="/api/v1", tags=["employer-private-code-fixtures"])
Principal = Annotated[AuthenticatedPrincipal, Depends(authenticated_principal)]


class PrivateCodeBundleReceipt(BaseModel):
    model_config = ConfigDict(extra="forbid")

    assessment_version_id: UUID
    source_sha256: str
    question_number: int
    language: Literal["python", "sql"]
    bundle_sha256: str
    sample_count: int
    hidden_count: int


class PrivateCodeFixtureStatus(BaseModel):
    """Public-review metadata only: never return testcase bodies or expected values."""

    model_config = ConfigDict(extra="forbid")

    question_number: int
    language: Literal["python", "sql"]
    ready: bool
    sample_count: int
    hidden_count: int
    bundle_sha256: str | None


@router.get(
    "/employer/assessments/{assessment_id}/code-test-bundles",
    response_model=list[PrivateCodeFixtureStatus],
)
def list_employer_code_fixture_status(
    assessment_id: UUID,
    engine: DatabaseEngine,
    principal: Principal,
) -> list[PrivateCodeFixtureStatus]:
    """Only employer owners/admins/reviewers can inspect fixture readiness."""
    with principal_transaction(engine, principal) as conn:
        _member(conn, principal, ("owner", "admin", "reviewer"))
        assessment = _org_assessment(conn, assessment_id)
        private = conn.execute(
            text(
                f"""SELECT source_sha256, private_rubric
                    FROM employer_assessment_private_keys
                    WHERE assessment_version_id=:assessment AND organization_id={_ORG}"""
            ),
            {"assessment": assessment_id},
        ).mappings().one_or_none()
        rubric = (
            private["private_rubric"]
            if private and private["source_sha256"] == assessment["content_sha256"]
            else {}
        )
        bundles = rubric.get("code_test_bundles", {})
        if not isinstance(bundles, dict):
            bundles = {}
        status: list[PrivateCodeFixtureStatus] = []
        for question in assessment["candidate_blueprint"]["questions"]:
            if question["kind"] != "code":
                continue
            number = str(question["number"])
            entry = bundles.get(number)
            ready = verified_code_fixtures(
                [question],
                assessment["content_sha256"],
                {"code_test_bundles": {number: entry}},
            )
            safe_entry = entry if ready and isinstance(entry, dict) else None
            cases = safe_entry["bundle"]["cases"] if safe_entry is not None else []
            status.append(PrivateCodeFixtureStatus(
                question_number=int(number),
                language=question["language"],
                ready=ready,
                sample_count=sum(case["visibility"] == "sample" for case in cases),
                hidden_count=sum(case["visibility"] == "hidden" for case in cases),
                bundle_sha256=(
                    safe_entry["bundle_sha256"] if safe_entry is not None else None
                ),
            ))
        return status


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
            raise HTTPException(
                status_code=409, detail="Published assessment fixtures are immutable"
            )
        questions = assessment["candidate_blueprint"]["questions"]
        question = next((q for q in questions if int(q["number"]) == question_number), None)
        if question is None or question["kind"] != "code":
            raise HTTPException(status_code=422, detail="Fixture target must be a coding question")
        if question.get("language") != payload.language:
            raise HTTPException(
                status_code=422, detail="Fixture runtime must equal published language"
            )
        if sum(case.points for case in payload.cases) != int(question["marks"]):
            raise HTTPException(
                status_code=422, detail="Hidden case points must equal question marks"
            )

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

        digest = canonical_bundle_digest(payload)
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
