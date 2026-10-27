"""Employer assessment authoring and candidate timed-session API.

No private rubric is returned in candidate responses. This is intentionally
independent of the personal mock-interview and practice-history APIs.
"""

from __future__ import annotations

import hashlib
import json
import secrets
from datetime import datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import Connection, text

from .auth import authenticated_principal
from .database import DatabaseEngine, principal_transaction
from .persistence import audit_event
from .schemas import AuthenticatedPrincipal

router = APIRouter(prefix="/api/v1", tags=["employer-assessments"])
Principal = Annotated[AuthenticatedPrincipal, Depends(authenticated_principal)]
_USER = "NULLIF(current_setting('rigor.user_id',true),'')::uuid"
_ORG = "NULLIF(current_setting('rigor.organization_id',true),'')::uuid"


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AssessmentQuestion(StrictModel):
    number: int = Field(ge=1, le=100)
    kind: Literal["code", "written", "multiple_choice"]
    prompt: str = Field(min_length=10, max_length=20_000)
    marks: int = Field(ge=1, le=100)
    options: list[str] = Field(default_factory=list, max_length=6)

    @model_validator(mode="after")
    def check_options(self) -> AssessmentQuestion:
        if self.kind == "multiple_choice":
            if len(self.options) != 4 or any(not v.strip() for v in self.options):
                raise ValueError("Single-answer MCQs require four nonempty public options")
        elif self.options:
            raise ValueError("Written and code problems do not have options")
        return self


class AssessmentDraftInput(StrictModel):
    slug: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{2,99}$")
    title: str = Field(min_length=5, max_length=160)
    duration_minutes: int = Field(ge=5, le=360)
    questions: list[AssessmentQuestion] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def unique_numbers(self) -> AssessmentDraftInput:
        if [q.number for q in self.questions] != list(range(1, len(self.questions) + 1)):
            raise ValueError("Questions must be sequential, unique, starting with 1")
        return self


class AssessmentView(StrictModel):
    id: UUID
    slug: str
    version: int
    title: str
    duration_minutes: int
    maximum_marks: int
    status: str
    content_sha256: str
    questions: list[AssessmentQuestion]


class PublishInput(StrictModel):
    rights_evidence: str = Field(min_length=10, max_length=500)
    technical_evidence: str = Field(min_length=10, max_length=500)
    editorial_evidence: str = Field(min_length=10, max_length=500)


class InviteInput(StrictModel):
    candidate_id: UUID
    expires_in_hours: int = Field(ge=1, le=168)


class InvitationCreated(StrictModel):
    id: UUID
    candidate_id: UUID
    expires_at: datetime
    acceptance_secret: str


class InvitationAccept(StrictModel):
    invitation_id: UUID
    acceptance_secret: str = Field(min_length=32, max_length=256)


class ResponseSave(StrictModel):
    question_number: int = Field(ge=1, le=100)
    answer_text: str = Field(min_length=1, max_length=100_000)


class AttemptView(StrictModel):
    id: UUID
    assessment_version_id: UUID
    status: str
    started_at: datetime | None
    deadline_at: datetime | None
    submitted_at: datetime | None
    duration_minutes: int
    questions: list[AssessmentQuestion]
    answers: dict[str, str]


def _member(conn: Connection, principal: AuthenticatedPrincipal, roles: tuple[str, ...]) -> None:
    if principal.organization_id is None:
        raise HTTPException(status_code=403, detail="Select an authorized employer organization")
    role = conn.execute(
        text(
            f"""SELECT role_slug FROM organization_memberships
                WHERE organization_id={_ORG} AND user_id={_USER}
                  AND status='active'"""
        )
    ).scalar_one_or_none()
    if role not in roles:
        raise HTTPException(status_code=403, detail="Employer organization permission required")


def _org_assessment(conn: Connection, assessment_id: UUID, *, lock: bool = False) -> dict[str, Any]:
    row = conn.execute(
        text(
            f"""SELECT id, slug, version, status, duration_minutes, maximum_marks,
                       candidate_blueprint, content_sha256, created_by
                FROM employer_assessment_versions
                WHERE id=:id AND organization_id={_ORG}
                {"FOR UPDATE" if lock else ""}"""
        ),
        {"id": assessment_id},
    ).mappings().one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Assessment not found")
    return dict(row)


def _assessment_view(row: dict[str, Any]) -> AssessmentView:
    data = row["candidate_blueprint"]
    return AssessmentView(
        id=row["id"],
        slug=row["slug"],
        version=row["version"],
        title=data["title"],
        duration_minutes=row["duration_minutes"],
        maximum_marks=row["maximum_marks"],
        status=row["status"],
        content_sha256=row["content_sha256"],
        questions=[AssessmentQuestion.model_validate(q) for q in data["questions"]],
    )


@router.post("/employer/assessments", response_model=AssessmentView, status_code=201)
def create_employer_assessment(
    payload: AssessmentDraftInput, engine: DatabaseEngine, principal: Principal,
) -> AssessmentView:
    blueprint = payload.model_dump(include={"title", "questions"})
    raw = json.dumps(blueprint, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(raw.encode()).hexdigest()
    with principal_transaction(engine, principal) as conn:
        _member(conn, principal, ("owner", "admin"))
        existing = conn.execute(
            text(
                f"""SELECT COALESCE(MAX(version), 0) FROM employer_assessment_versions
                    WHERE organization_id={_ORG} AND slug=:slug"""
            ),
            {"slug": payload.slug},
        ).scalar_one()
        row = conn.execute(
            text(
                f"""INSERT INTO employer_assessment_versions
                       (organization_id, slug, version, status, duration_minutes,
                        maximum_marks, candidate_blueprint, content_sha256, created_by)
                    VALUES ({_ORG}, :slug, :version, 'review_required', :minutes,
                            :marks, CAST(:blueprint AS jsonb), :digest, {_USER})
                    RETURNING id, slug, version, status, duration_minutes, maximum_marks,
                              candidate_blueprint, content_sha256, created_by"""
            ),
            {
                "slug": payload.slug,
                "version": int(existing) + 1,
                "minutes": payload.duration_minutes,
                "marks": sum(q.marks for q in payload.questions),
                "blueprint": raw,
                "digest": digest,
            },
        ).mappings().one()
        audit_event(
            conn, principal, row["created_by"], action="assessment.draft",
            resource_type="employer_assessment", resource_id=str(row["id"]),
            details={"hash": digest},
        )
        return _assessment_view(dict(row))


@router.get("/employer/assessments", response_model=list[AssessmentView])
def list_employer_assessments(
    engine: DatabaseEngine, principal: Principal,
) -> list[AssessmentView]:
    with principal_transaction(engine, principal) as conn:
        _member(conn, principal, ("owner", "admin", "recruiter", "interviewer", "reviewer"))
        rows = conn.execute(
            text(
                f"""SELECT id, slug, version, status, duration_minutes, maximum_marks,
                           candidate_blueprint, content_sha256
                    FROM employer_assessment_versions
                    WHERE organization_id={_ORG} ORDER BY created_at DESC LIMIT 100"""
            )
        ).mappings().all()
        return [_assessment_view(dict(row)) for row in rows]


@router.post("/employer/assessments/{assessment_id}/publish", response_model=AssessmentView)
def publish_employer_assessment(
    assessment_id: UUID, payload: PublishInput, engine: DatabaseEngine, principal: Principal,
) -> AssessmentView:
    with principal_transaction(engine, principal) as conn:
        _member(conn, principal, ("reviewer", "admin"))
        row = _org_assessment(conn, assessment_id, lock=True)
        reviewer = conn.execute(text(f"SELECT {_USER}")).scalar_one()
        if row["created_by"] == reviewer:
            raise HTTPException(status_code=409, detail="An independent reviewer is required")
        if row["status"] != "review_required":
            raise HTTPException(status_code=409, detail="Assessment is not awaiting review")
        updated = conn.execute(
            text(
                f"""UPDATE employer_assessment_versions
                    SET status='published', approved_at=CURRENT_TIMESTAMP
                    WHERE id=:id AND organization_id={_ORG}
                    RETURNING id, slug, version, status, duration_minutes,
                              maximum_marks, candidate_blueprint, content_sha256"""
            ), {"id": assessment_id},
        ).mappings().one()
        audit_event(
            conn, principal, reviewer, action="assessment.publish",
            resource_type="employer_assessment", resource_id=str(assessment_id),
            details=payload.model_dump(),
        )
        return _assessment_view(dict(updated))


@router.post(
    "/employer/assessments/{assessment_id}/invitations",
    response_model=InvitationCreated, status_code=201,
)
def create_employer_invitation(
    assessment_id: UUID, payload: InviteInput, engine: DatabaseEngine, principal: Principal,
) -> InvitationCreated:
    with principal_transaction(engine, principal) as conn:
        _member(conn, principal, ("owner", "admin", "recruiter"))
        assessment = _org_assessment(conn, assessment_id)
        if assessment["status"] != "published":
            raise HTTPException(status_code=409, detail="Assessment has not been published")
        secret = secrets.token_urlsafe(48)
        digest = hashlib.sha256(secret.encode()).hexdigest()
        candidate = conn.execute(
            text("SELECT id FROM users WHERE id=:candidate AND status='active'"),
            {"candidate": payload.candidate_id},
        ).scalar_one_or_none()
        if candidate is None:
            raise HTTPException(status_code=404, detail="Candidate not registered")
        row = conn.execute(
            text(
                f"""INSERT INTO employer_assessment_invitations
                       (organization_id, assessment_version_id, candidate_id,
                        invited_by, token_digest, expires_at)
                    VALUES ({_ORG}, :assessment, :candidate, {_USER}, :digest,
                            CURRENT_TIMESTAMP + make_interval(hours => :hours))
                    RETURNING id, candidate_id, expires_at"""
            ), {
                "assessment": assessment_id, "candidate": payload.candidate_id,
                "digest": digest, "hours": payload.expires_in_hours,
            },
        ).mappings().one()
        actor = conn.execute(text(f"SELECT {_USER}")).scalar_one()
        audit_event(
            conn, principal, actor, action="assessment.invite",
            resource_type="employer_invitation", resource_id=str(row["id"]),
            details={"candidate_id": str(payload.candidate_id)},
        )
        return InvitationCreated(
            id=row["id"], candidate_id=row["candidate_id"],
            expires_at=row["expires_at"], acceptance_secret=secret,
        )


def _candidate_attempt(conn: Connection, attempt_id: UUID, *, lock: bool = False) -> dict[str, Any]:
    row = conn.execute(
        text(
            f"""SELECT a.id, a.status, a.started_at, a.deadline_at, a.submitted_at,
                       a.candidate_id, i.assessment_version_id,
                       v.candidate_blueprint, v.duration_minutes
                FROM employer_assessment_attempts a
                JOIN employer_assessment_invitations i ON i.id=a.invitation_id
                JOIN employer_assessment_versions v ON v.id=i.assessment_version_id
                WHERE a.id=:attempt AND a.candidate_id={_USER}
                {"FOR UPDATE OF a" if lock else ""}"""
        ), {"attempt": attempt_id},
    ).mappings().one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Assessment attempt not found")
    return dict(row)


def _attempt_view(conn: Connection, row: dict) -> AttemptView:
    answers = conn.execute(
        text(
            f"""SELECT question_number, answer_text FROM employer_assessment_responses
                WHERE attempt_id=:attempt AND candidate_id={_USER}"""
        ), {"attempt": row["id"]},
    ).all()
    return AttemptView(
        id=row["id"], assessment_version_id=row["assessment_version_id"],
        status=row["status"], started_at=row["started_at"],
        deadline_at=row["deadline_at"], submitted_at=row["submitted_at"],
        duration_minutes=row["duration_minutes"],
        questions=[
            AssessmentQuestion.model_validate(q)
            for q in row["candidate_blueprint"]["questions"]
        ],
        answers={str(number): text_value for number, text_value in answers},
    )


@router.post("/assessment-invitations/accept", response_model=AttemptView)
def accept_assessment_invitation(
    payload: InvitationAccept, engine: DatabaseEngine, principal: Principal,
) -> AttemptView:
    digest = hashlib.sha256(payload.acceptance_secret.encode()).hexdigest()
    with principal_transaction(engine, principal) as conn:
        row = conn.execute(
            text(
                f"""SELECT i.id, i.organization_id, i.assessment_version_id,
                           i.state, i.expires_at
                    FROM employer_assessment_invitations i
                    WHERE i.id=:id AND i.candidate_id={_USER} AND i.token_digest=:digest
                    FOR UPDATE OF i"""
            ), {"id": payload.invitation_id, "digest": digest},
        ).mappings().one_or_none()
        if row is None:
            raise HTTPException(status_code=404, detail="Valid invitation not found")
        if row["state"] != "pending":
            raise HTTPException(status_code=409, detail="Invitation already used or revoked")
        if row["expires_at"] <= conn.execute(text("SELECT CURRENT_TIMESTAMP")).scalar_one():
            raise HTTPException(status_code=410, detail="Invitation has expired")
        conn.execute(
            text(
                "UPDATE employer_assessment_invitations "
                "SET state='accepted', consumed_at=CURRENT_TIMESTAMP WHERE id=:id"
            ), {"id": row["id"]},
        )
        version = conn.execute(
            text(
                """SELECT duration_minutes, status
                   FROM employer_assessment_versions WHERE id=:assessment"""
            ),
            {"assessment": row["assessment_version_id"]},
        ).mappings().one_or_none()
        if version is None or version["status"] != "published":
            raise HTTPException(status_code=409, detail="Assessment is no longer available")
        attempt = conn.execute(
            text(
                f"""INSERT INTO employer_assessment_attempts
                       (organization_id, invitation_id, candidate_id, status,
                        started_at, deadline_at)
                    VALUES (:org, :invitation, {_USER}, 'in_progress',
                            CURRENT_TIMESTAMP,
                            CURRENT_TIMESTAMP + make_interval(mins => :minutes))
                    RETURNING id"""
            ), {
                "org": row["organization_id"], "invitation": row["id"],
                "minutes": version["duration_minutes"],
            },
        ).scalar_one()
        return _attempt_view(conn, _candidate_attempt(conn, attempt))


@router.get("/assessment-attempts/{attempt_id}", response_model=AttemptView)
def get_assessment_attempt(
    attempt_id: UUID, engine: DatabaseEngine, principal: Principal,
) -> AttemptView:
    with principal_transaction(engine, principal) as conn:
        return _attempt_view(conn, _candidate_attempt(conn, attempt_id))


@router.put("/assessment-attempts/{attempt_id}/responses", response_model=AttemptView)
def save_assessment_response(
    attempt_id: UUID, payload: ResponseSave, engine: DatabaseEngine, principal: Principal,
) -> AttemptView:
    with principal_transaction(engine, principal) as conn:
        row = _candidate_attempt(conn, attempt_id, lock=True)
        now = conn.execute(text("SELECT CURRENT_TIMESTAMP")).scalar_one()
        if row["status"] != "in_progress" or row["deadline_at"] <= now:
            raise HTTPException(status_code=409, detail="Attempt is no longer accepting responses")
        if payload.question_number > len(row["candidate_blueprint"]["questions"]):
            raise HTTPException(status_code=422, detail="Unknown assessment question")
        conn.execute(
            text(
                f"""INSERT INTO employer_assessment_responses
                       (organization_id, attempt_id, candidate_id, question_number,
                        answer_text, answer_sha256)
                    VALUES ((SELECT organization_id FROM employer_assessment_attempts
                             WHERE id=:attempt), :attempt, {_USER}, :number, :answer, :digest)
                    ON CONFLICT (attempt_id, question_number)
                    DO UPDATE SET answer_text=EXCLUDED.answer_text,
                                  answer_sha256=EXCLUDED.answer_sha256,
                                  updated_at=CURRENT_TIMESTAMP"""
            ), {
                "attempt": attempt_id, "number": payload.question_number,
                "answer": payload.answer_text,
                "digest": hashlib.sha256(payload.answer_text.encode()).hexdigest(),
            },
        )
        return _attempt_view(conn, row)


@router.post("/assessment-attempts/{attempt_id}/submit", response_model=AttemptView)
def submit_assessment_attempt(
    attempt_id: UUID, engine: DatabaseEngine, principal: Principal,
) -> AttemptView:
    with principal_transaction(engine, principal) as conn:
        row = _candidate_attempt(conn, attempt_id, lock=True)
        if row["status"] not in {"in_progress", "expired", "submitted"}:
            raise HTTPException(status_code=409, detail="Invalid attempt state")
        if row["status"] == "in_progress":
            new_status = (
                "expired"
                if row["deadline_at"] <= conn.execute(text("SELECT CURRENT_TIMESTAMP")).scalar_one()
                else "submitted"
            )
            conn.execute(
                text(
                    """UPDATE employer_assessment_attempts
                       SET status=:status, submitted_at=CURRENT_TIMESTAMP
                       WHERE id=:id"""
                ), {"status": new_status, "id": attempt_id},
            )
        return _attempt_view(conn, _candidate_attempt(conn, attempt_id))
