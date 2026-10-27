"""Employer-facing assessment reports and independently reviewed AI transcripts.

No raw private keys, unreviewed scoring, or AI-driven hiring decisions are
included in reports. CSV cells consist only of server-generated identifiers,
timestamps, integer marks and fixed states (no spreadsheet formulas).
"""

from __future__ import annotations

import csv
import io
from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict
from sqlalchemy import Connection, text

from .auth import authenticated_principal
from .database import DatabaseEngine, principal_transaction
from .employer_assessment_routes import _employer_attempt, _member, _org_assessment
from .schemas import AuthenticatedPrincipal

router = APIRouter(prefix="/api/v1/employer", tags=["employer-reporting"])
Principal = Annotated[AuthenticatedPrincipal, Depends(authenticated_principal)]
_ORG = "NULLIF(current_setting('rigor.organization_id',true),'')::uuid"


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ReviewSummary(StrictModel):
    reviewer_id: UUID
    review_id: UUID
    awarded_marks: int
    maximum_marks: int
    submitted_at: datetime


class ReportAttempt(StrictModel):
    attempt_id: UUID
    candidate_id: UUID
    state: str
    started_at: datetime | None
    submitted_at: datetime | None
    human_reviews: list[ReviewSummary]
    hiring_decision: None = None


class EmployerAssessmentReport(StrictModel):
    assessment_version_id: UUID
    content_sha256: str
    maximum_marks: int
    total_invitations: int
    accepted_invitations: int
    pending_invitations: int
    revoked_invitations: int
    total_attempts: int
    submitted_attempts: int
    human_reviewed_attempts: int
    attempts: list[ReportAttempt]


class TranscriptTurn(StrictModel):
    sequence_number: int
    role: str
    content: str
    created_at: datetime


class EmployerTranscript(StrictModel):
    attempt_id: UUID
    session_id: UUID
    consent_version: str
    consent_at: datetime
    status: str
    turns: list[TranscriptTurn]
    automated_hiring_decision: None = None


def _load_report(conn: Connection, assessment_id: UUID) -> EmployerAssessmentReport:
    version = _org_assessment(conn, assessment_id)
    invitation_rows = conn.execute(
        text(
            f"""SELECT state, COUNT(*) AS count
                FROM employer_assessment_invitations
                WHERE assessment_version_id=:assessment
                  AND organization_id={_ORG}
                GROUP BY state"""
        ),
        {"assessment": assessment_id},
    ).mappings().all()
    counts = {str(row["state"]): int(row["count"]) for row in invitation_rows}
    attempts = conn.execute(
        text(
            f"""SELECT a.id, a.candidate_id, a.status, a.started_at, a.submitted_at
                FROM employer_assessment_attempts a
                JOIN employer_assessment_invitations i
                  ON i.id=a.invitation_id AND i.organization_id=a.organization_id
                WHERE a.organization_id={_ORG}
                  AND i.assessment_version_id=:assessment
                ORDER BY a.created_at DESC LIMIT 500"""
        ),
        {"assessment": assessment_id},
    ).mappings().all()
    output = []
    reviewed_count = 0
    for attempt in attempts:
        reviews = conn.execute(
            text(
                f"""SELECT id, reviewer_id, evidence, created_at
                    FROM employer_assessment_reviews
                    WHERE organization_id={_ORG} AND attempt_id=:attempt
                      AND status IN ('submitted','adjudicated')
                    ORDER BY created_at ASC"""
            ),
            {"attempt": attempt["id"]},
        ).mappings().all()
        receipts = [
            ReviewSummary(
                reviewer_id=item["reviewer_id"],
                review_id=item["id"],
                awarded_marks=int(item["evidence"]["awarded_marks"]),
                maximum_marks=int(item["evidence"]["maximum_marks"]),
                submitted_at=item["created_at"],
            )
            for item in reviews
        ]
        if receipts:
            reviewed_count += 1
        output.append(
            ReportAttempt(
                attempt_id=attempt["id"],
                candidate_id=attempt["candidate_id"],
                state=attempt["status"],
                started_at=attempt["started_at"],
                submitted_at=attempt["submitted_at"],
                human_reviews=receipts,
            )
        )
    return EmployerAssessmentReport(
        assessment_version_id=assessment_id,
        content_sha256=version["content_sha256"],
        maximum_marks=version["maximum_marks"],
        total_invitations=sum(counts.values()),
        accepted_invitations=counts.get("accepted", 0),
        pending_invitations=counts.get("pending", 0),
        revoked_invitations=counts.get("revoked", 0),
        total_attempts=len(output),
        submitted_attempts=sum(item.state == "submitted" for item in output),
        human_reviewed_attempts=reviewed_count,
        attempts=output,
    )


@router.get(
    "/assessments/{assessment_id}/report",
    response_model=EmployerAssessmentReport,
)
def employer_assessment_report(
    assessment_id: UUID, engine: DatabaseEngine, principal: Principal,
) -> EmployerAssessmentReport:
    with principal_transaction(engine, principal) as conn:
        _member(conn, principal, ("owner", "admin", "recruiter", "reviewer"))
        return _load_report(conn, assessment_id)


@router.get("/assessments/{assessment_id}/report.csv")
def export_employer_assessment_csv(
    assessment_id: UUID, engine: DatabaseEngine, principal: Principal,
) -> Response:
    with principal_transaction(engine, principal) as conn:
        _member(conn, principal, ("owner", "admin", "recruiter", "reviewer"))
        report = _load_report(conn, assessment_id)
    csv_buffer = io.StringIO(newline="")
    writer = csv.writer(csv_buffer, lineterminator="\r\n")
    writer.writerow([
        "assessment_version_id", "candidate_id", "attempt_id",
        "attempt_state", "started_at_utc", "submitted_at_utc",
        "review_id", "reviewer_id", "human_awarded_marks",
        "human_maximum_marks", "human_reviewed_at_utc",
    ])
    for attempt in report.attempts:
        for review in attempt.human_reviews or [None]:
            writer.writerow([
                str(report.assessment_version_id),
                str(attempt.candidate_id),
                str(attempt.attempt_id),
                attempt.state,
                attempt.started_at.isoformat() if attempt.started_at else "",
                attempt.submitted_at.isoformat() if attempt.submitted_at else "",
                str(review.review_id) if review else "",
                str(review.reviewer_id) if review else "",
                review.awarded_marks if review else "",
                review.maximum_marks if review else "",
                review.submitted_at.isoformat() if review else "",
            ])
    return Response(
        content=csv_buffer.getvalue(), media_type="text/csv",
        headers={
            "Content-Disposition": (
                f'attachment; filename="skillforge-assessment-{assessment_id}.csv"'
            ),
            "Cache-Control": "no-store",
        },
    )


@router.get("/attempts/{attempt_id}/ai-interview", response_model=EmployerTranscript)
def employer_interview_transcript(
    attempt_id: UUID, engine: DatabaseEngine, principal: Principal,
) -> EmployerTranscript:
    """Make an opted-in interview transcript available after submission only."""
    with principal_transaction(engine, principal) as conn:
        _member(conn, principal, ("owner", "admin", "reviewer", "interviewer"))
        attempt = _employer_attempt(conn, attempt_id)
        if attempt["status"] != "submitted":
            raise HTTPException(
                status_code=409, detail="Transcript releases only after assessment submission"
            )
        session = conn.execute(
            text(
                f"""SELECT id, consent_version, consent_at, status
                    FROM employer_ai_interview_sessions
                    WHERE organization_id={_ORG} AND attempt_id=:attempt"""
            ), {"attempt": attempt_id},
        ).mappings().one_or_none()
        if session is None or session["status"] == "erased":
            raise HTTPException(status_code=404, detail="No retained AI interview transcript")
        rows = conn.execute(
            text(
                f"""SELECT sequence_number, role, content, created_at
                    FROM employer_ai_interview_messages
                    WHERE organization_id={_ORG} AND session_id=:session
                    ORDER BY sequence_number"""
            ), {"session": session["id"]},
        ).mappings().all()
        return EmployerTranscript(
            attempt_id=attempt_id, session_id=session["id"],
            consent_version=session["consent_version"],
            consent_at=session["consent_at"], status=session["status"],
            turns=[TranscriptTurn.model_validate(dict(row)) for row in rows],
        )
