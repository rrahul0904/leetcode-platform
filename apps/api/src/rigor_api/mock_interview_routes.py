from __future__ import annotations

import json
from datetime import datetime
from typing import Annotated, Any, Literal, cast
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import Connection, text

from .auth import require_permissions
from .database import DatabaseEngine, principal_transaction
from .mock_interview_domain import (
    PhaseEvidence,
    build_report,
    evaluate_response,
    template_for,
    templates,
)
from .schemas import AuthenticatedPrincipal, InterviewMessage, MockInterviewState

router = APIRouter(prefix="/api/v1/mock-interviews", tags=["mock-interviews"])

_CURRENT_USER_SQL = "NULLIF(current_setting('rigor.user_id', true), '')::uuid"
_EVALUATOR_VERSION = "mock-interview-rubric-v1"
_READINESS_VERSION = "weighted-evidence-v2-mock-interview"


class MockInterviewModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class MockInterviewTemplateView(MockInterviewModel):
    slug: str
    label: str
    description: str
    competencies: list[str]
    phases: list[dict[str, str]]


class MockInterviewCreate(MockInterviewModel):
    focus: str = Field(min_length=2, max_length=80)
    target_role: str = Field(min_length=2, max_length=160)


class MockInterviewResponseInput(MockInterviewModel):
    content: str = Field(min_length=1, max_length=50_000)


class MockInterviewActionInput(MockInterviewModel):
    action: Literal["pause", "resume", "cancel"]


class MockInterviewReportView(MockInterviewModel):
    overall_score: float = Field(ge=0, le=1)
    rubric_evidence: list[dict[str, object]]
    strengths: list[str]
    growth_areas: list[str]
    next_steps: list[str]


class MockInterviewSessionSummary(MockInterviewModel):
    id: UUID
    interview_type: str
    target_role: str
    focus: str
    focus_label: str
    status: MockInterviewState
    current_phase: str
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class MockInterviewSessionView(MockInterviewSessionSummary):
    messages: list[InterviewMessage]
    report: MockInterviewReportView | None


MockReadPrincipal = Annotated[
    AuthenticatedPrincipal,
    Depends(require_permissions("submission:read-own")),
]
MockWritePrincipal = Annotated[
    AuthenticatedPrincipal,
    Depends(require_permissions("submission:create")),
]
IdempotencyHeader = Annotated[
    str,
    Header(alias="Idempotency-Key", min_length=8, max_length=160),
]


def _template_view(slug: str) -> MockInterviewTemplateView:
    template = template_for(slug)
    if template is None:
        raise HTTPException(status_code=404, detail="Mock interview template not found")
    return MockInterviewTemplateView(
        slug=template.slug,
        label=template.label,
        description=template.description,
        competencies=list(template.competencies),
        phases=[
            {"slug": phase.slug, "label": phase.label}
            for phase in template.phases
        ],
    )


def _summary(row: Any) -> MockInterviewSessionSummary:
    focus = str(row["source_id"])
    template = template_for(focus)
    return MockInterviewSessionSummary(
        id=UUID(str(row["id"])),
        interview_type=str(row["interview_type"]),
        target_role=str(row["target_role"]),
        focus=focus,
        focus_label=template.label if template is not None else focus,
        status=MockInterviewState(str(row["status"])),
        current_phase=str(row["current_phase"]),
        started_at=row["started_at"],
        completed_at=row["completed_at"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _session_row(connection: Connection, session_id: UUID, *, lock: bool = False) -> Any:
    suffix = " FOR UPDATE" if lock else ""
    row = connection.execute(
        text(
            f"""
            SELECT id, interview_type, target_role, source_type, source_id,
                   status, current_phase, started_at, completed_at,
                   created_at, updated_at
            FROM mock_interview_sessions
            WHERE id=:session_id
              AND candidate_id={_CURRENT_USER_SQL}
            {suffix}
            """
        ),
        {"session_id": session_id},
    ).mappings().one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Mock interview session not found")
    return row


def _messages(connection: Connection, session_id: UUID) -> list[InterviewMessage]:
    rows = connection.execute(
        text(
            """
            SELECT id, session_id, sequence_number, role, phase,
                   content, evidence, created_at
            FROM mock_interview_messages
            WHERE session_id=:session_id
            ORDER BY sequence_number
            """
        ),
        {"session_id": session_id},
    ).mappings().all()
    return [InterviewMessage.model_validate(dict(row)) for row in rows]


def _report(
    connection: Connection,
    session_id: UUID,
) -> MockInterviewReportView | None:
    row = connection.execute(
        text(
            """
            SELECT overall_score, rubric_evidence, strengths,
                   growth_areas, next_steps
            FROM mock_interview_reports
            WHERE session_id=:session_id
            """
        ),
        {"session_id": session_id},
    ).mappings().one_or_none()
    if row is None:
        return None
    return MockInterviewReportView(
        overall_score=float(row["overall_score"]),
        rubric_evidence=cast(list[dict[str, object]], row["rubric_evidence"]),
        strengths=[str(item) for item in cast(list[object], row["strengths"])],
        growth_areas=[
            str(item) for item in cast(list[object], row["growth_areas"])
        ],
        next_steps=[str(item) for item in cast(list[object], row["next_steps"])],
    )


def _detail(connection: Connection, session_id: UUID) -> MockInterviewSessionView:
    row = _session_row(connection, session_id)
    return MockInterviewSessionView(
        **_summary(row).model_dump(),
        messages=_messages(connection, session_id),
        report=_report(connection, session_id),
    )


def _next_sequence(connection: Connection, session_id: UUID) -> int:
    value = connection.execute(
        text(
            """
            SELECT COALESCE(max(sequence_number), -1) + 1
            FROM mock_interview_messages
            WHERE session_id=:session_id
            """
        ),
        {"session_id": session_id},
    ).scalar_one()
    return int(value)


def _insert_message(
    connection: Connection,
    *,
    session_id: UUID,
    role: str,
    phase: str,
    content: str,
    evidence: dict[str, object],
) -> None:
    connection.execute(
        text(
            """
            INSERT INTO mock_interview_messages (
                session_id, sequence_number, role, phase, content, evidence
            ) VALUES (
                :session_id, :sequence_number, :role, :phase,
                :content, CAST(:evidence AS jsonb)
            )
            """
        ),
        {
            "session_id": session_id,
            "sequence_number": _next_sequence(connection, session_id),
            "role": role,
            "phase": phase,
            "content": content,
            "evidence": json.dumps(evidence, separators=(",", ":")),
        },
    )


def _phase_evidence_from_messages(
    connection: Connection,
    session_id: UUID,
) -> list[PhaseEvidence]:
    rows = connection.execute(
        text(
            """
            SELECT phase, evidence
            FROM mock_interview_messages
            WHERE session_id=:session_id
              AND role='candidate'
            ORDER BY sequence_number
            """
        ),
        {"session_id": session_id},
    ).mappings().all()
    evidence: list[PhaseEvidence] = []
    for row in rows:
        payload = (
            cast(dict[str, object], row["evidence"])
            if isinstance(row["evidence"], dict)
            else {}
        )
        evidence.append(
            PhaseEvidence(
                phase=str(row["phase"]),
                label=str(payload.get("label") or row["phase"]),
                score=float(payload.get("score") or 0),
                concept_coverage=float(payload.get("concept_coverage") or 0),
                depth_score=float(payload.get("depth_score") or 0),
                matched_concepts=tuple(
                    str(item)
                    for item in cast(
                        list[object],
                        payload.get("matched_concepts") or [],
                    )
                ),
                missing_concepts=tuple(
                    str(item)
                    for item in cast(
                        list[object],
                        payload.get("missing_concepts") or [],
                    )
                ),
                word_count=int(payload.get("word_count") or 0),
            )
        )
    return evidence


def _write_mastery(
    connection: Connection,
    *,
    session_id: UUID,
    organization_id: str | None,
    competency_slug: str,
    score: float,
    phase_count: int,
) -> None:
    competency_id = connection.execute(
        text("SELECT id FROM competencies WHERE slug=:slug"),
        {"slug": competency_slug},
    ).scalar_one_or_none()
    if competency_id is None:
        return

    confidence = min(0.9, 0.55 + (0.05 * phase_count))
    weight = 0.75
    connection.execute(
        text(
            f"""
            INSERT INTO candidate_competency_evidence (
                organization_id, candidate_id, competency_id, source_type,
                source_id, score, confidence, weight, evaluator_version,
                observed_at, evidence
            ) VALUES (
                CAST(NULLIF(:organization_id, '') AS uuid),
                {_CURRENT_USER_SQL}, :competency_id, 'MOCK_INTERVIEW',
                :source_id, :score, :confidence, :weight, :evaluator_version,
                CURRENT_TIMESTAMP, CAST(:evidence AS jsonb)
            )
            ON CONFLICT (
                candidate_id, source_type, source_id, competency_id
            ) DO NOTHING
            """
        ),
        {
            "organization_id": organization_id or "",
            "competency_id": competency_id,
            "source_id": str(session_id),
            "score": score,
            "confidence": confidence,
            "weight": weight,
            "evaluator_version": _EVALUATOR_VERSION,
            "evidence": json.dumps(
                {
                    "session_id": str(session_id),
                    "phase_count": phase_count,
                    "rubric": _EVALUATOR_VERSION,
                },
                separators=(",", ":"),
            ),
        },
    )
    aggregate = connection.execute(
        text(
            f"""
            SELECT sum(score * confidence * weight)
                       / NULLIF(sum(confidence * weight), 0) AS mastery,
                   1 - exp(-sum(confidence * weight) / 3.0) AS confidence,
                   count(*) AS evidence_count,
                   max(observed_at) AS last_evidence_at
            FROM candidate_competency_evidence
            WHERE candidate_id={_CURRENT_USER_SQL}
              AND competency_id=:competency_id
            """
        ),
        {"competency_id": competency_id},
    ).mappings().one()
    connection.execute(
        text(
            f"""
            INSERT INTO candidate_competency_mastery (
                organization_id, candidate_id, competency_id, mastery,
                confidence, evidence_count, last_evidence_at,
                calculation_version
            ) VALUES (
                CAST(NULLIF(:organization_id, '') AS uuid),
                {_CURRENT_USER_SQL}, :competency_id, :mastery,
                :confidence, :evidence_count, :last_evidence_at, :version
            )
            ON CONFLICT (candidate_id, competency_id) DO UPDATE SET
                mastery=EXCLUDED.mastery,
                confidence=EXCLUDED.confidence,
                evidence_count=EXCLUDED.evidence_count,
                last_evidence_at=EXCLUDED.last_evidence_at,
                calculation_version=EXCLUDED.calculation_version,
                updated_at=CURRENT_TIMESTAMP
            """
        ),
        {
            "organization_id": organization_id or "",
            "competency_id": competency_id,
            "mastery": aggregate["mastery"],
            "confidence": aggregate["confidence"],
            "evidence_count": aggregate["evidence_count"],
            "last_evidence_at": aggregate["last_evidence_at"],
            "version": _READINESS_VERSION,
        },
    )


def _complete_session(
    connection: Connection,
    *,
    session_id: UUID,
    organization_id: str | None,
    focus: str,
) -> None:
    template = template_for(focus)
    if template is None:
        raise HTTPException(status_code=409, detail="Interview template is unavailable")
    report = build_report(_phase_evidence_from_messages(connection, session_id))
    rubric_payload = [
        {
            "phase": item.phase,
            "label": item.label,
            "score": item.score,
            "concept_coverage": item.concept_coverage,
            "depth_score": item.depth_score,
            "matched_concepts": list(item.matched_concepts),
            "missing_concepts": list(item.missing_concepts),
            "word_count": item.word_count,
        }
        for item in report.rubric_evidence
    ]
    connection.execute(
        text(
            """
            INSERT INTO mock_interview_reports (
                session_id, overall_score, rubric_evidence,
                strengths, growth_areas, next_steps
            ) VALUES (
                :session_id, :overall_score, CAST(:rubric_evidence AS jsonb),
                CAST(:strengths AS jsonb), CAST(:growth_areas AS jsonb),
                CAST(:next_steps AS jsonb)
            )
            ON CONFLICT (session_id) DO NOTHING
            """
        ),
        {
            "session_id": session_id,
            "overall_score": report.overall_score,
            "rubric_evidence": json.dumps(
                rubric_payload,
                separators=(",", ":"),
            ),
            "strengths": json.dumps(list(report.strengths)),
            "growth_areas": json.dumps(list(report.growth_areas)),
            "next_steps": json.dumps(list(report.next_steps)),
        },
    )
    connection.execute(
        text(
            f"""
            UPDATE mock_interview_sessions
            SET status='COMPLETED'::mock_interview_state,
                current_phase='COMPLETE',
                completed_at=CURRENT_TIMESTAMP,
                updated_at=CURRENT_TIMESTAMP
            WHERE id=:session_id
              AND candidate_id={_CURRENT_USER_SQL}
            """
        ),
        {"session_id": session_id},
    )
    for competency_slug in template.competencies:
        _write_mastery(
            connection,
            session_id=session_id,
            organization_id=organization_id,
            competency_slug=competency_slug,
            score=report.overall_score,
            phase_count=len(report.rubric_evidence),
        )


@router.get("/templates", response_model=list[MockInterviewTemplateView])
def list_mock_interview_templates(
    _principal: MockReadPrincipal,
) -> list[MockInterviewTemplateView]:
    return [_template_view(template.slug) for template in templates()]


@router.post("", response_model=MockInterviewSessionView, status_code=201)
def create_mock_interview(
    request: MockInterviewCreate,
    principal: MockWritePrincipal,
    engine: DatabaseEngine,
    idempotency_key: IdempotencyHeader,
) -> MockInterviewSessionView:
    template = template_for(request.focus)
    if template is None:
        raise HTTPException(status_code=404, detail="Mock interview template not found")

    with principal_transaction(engine, principal) as connection:
        existing = connection.execute(
            text(
                f"""
                SELECT id
                FROM mock_interview_sessions
                WHERE candidate_id={_CURRENT_USER_SQL}
                  AND source_type='skillforge_template'
                  AND source_id=:source_id
                  AND current_phase LIKE :idempotency_marker
                ORDER BY created_at DESC
                LIMIT 1
                """
            ),
            {
                "source_id": template.slug,
                "idempotency_marker": f"%|{idempotency_key}",
            },
        ).scalar_one_or_none()
        if existing is not None:
            return _detail(connection, UUID(str(existing)))

        first_phase = template.phases[0]
        session_id = connection.execute(
            text(
                f"""
                INSERT INTO mock_interview_sessions (
                    organization_id, candidate_id, interview_type,
                    target_role, source_type, source_id, status,
                    current_phase, started_at
                ) VALUES (
                    CAST(NULLIF(:organization_id, '') AS uuid),
                    {_CURRENT_USER_SQL}, 'TECHNICAL_MOCK',
                    :target_role, 'skillforge_template', :source_id,
                    'IN_PROGRESS'::mock_interview_state,
                    :current_phase, CURRENT_TIMESTAMP
                )
                RETURNING id
                """
            ),
            {
                "organization_id": principal.organization_id or "",
                "target_role": request.target_role.strip(),
                "source_id": template.slug,
                "current_phase": f"{first_phase.slug}|{idempotency_key}",
            },
        ).scalar_one()
        resolved_session_id = UUID(str(session_id))
        _insert_message(
            connection,
            session_id=resolved_session_id,
            role="interviewer",
            phase=first_phase.slug,
            content=first_phase.prompt,
            evidence={
                "template": template.slug,
                "label": first_phase.label,
                "rubric": _EVALUATOR_VERSION,
            },
        )
        connection.execute(
            text(
                """
                UPDATE mock_interview_sessions
                SET current_phase=:phase
                WHERE id=:session_id
                """
            ),
            {"phase": first_phase.slug, "session_id": resolved_session_id},
        )
        return _detail(connection, resolved_session_id)


@router.get("", response_model=list[MockInterviewSessionSummary])
def list_mock_interviews(
    principal: MockReadPrincipal,
    engine: DatabaseEngine,
) -> list[MockInterviewSessionSummary]:
    with principal_transaction(engine, principal) as connection:
        rows = connection.execute(
            text(
                f"""
                SELECT id, interview_type, target_role, source_type, source_id,
                       status, current_phase, started_at, completed_at,
                       created_at, updated_at
                FROM mock_interview_sessions
                WHERE candidate_id={_CURRENT_USER_SQL}
                ORDER BY updated_at DESC
                LIMIT 50
                """
            )
        ).mappings().all()
        return [_summary(row) for row in rows]


@router.get("/{session_id}", response_model=MockInterviewSessionView)
def get_mock_interview(
    session_id: UUID,
    principal: MockReadPrincipal,
    engine: DatabaseEngine,
) -> MockInterviewSessionView:
    with principal_transaction(engine, principal) as connection:
        return _detail(connection, session_id)


@router.post(
    "/{session_id}/responses",
    response_model=MockInterviewSessionView,
)
def answer_mock_interview(
    session_id: UUID,
    request: MockInterviewResponseInput,
    principal: MockWritePrincipal,
    engine: DatabaseEngine,
    idempotency_key: IdempotencyHeader,
) -> MockInterviewSessionView:
    with principal_transaction(engine, principal) as connection:
        row = _session_row(connection, session_id, lock=True)
        existing = connection.execute(
            text(
                """
                SELECT 1
                FROM mock_interview_messages
                WHERE session_id=:session_id
                  AND role='candidate'
                  AND evidence->>'idempotency_key'=:idempotency_key
                LIMIT 1
                """
            ),
            {
                "session_id": session_id,
                "idempotency_key": idempotency_key,
            },
        ).scalar_one_or_none()
        if existing is not None:
            return _detail(connection, session_id)

        status = MockInterviewState(str(row["status"]))
        if status is not MockInterviewState.in_progress:
            raise HTTPException(
                status_code=409,
                detail="Only an in-progress mock interview accepts responses.",
            )
        focus = str(row["source_id"])
        template = template_for(focus)
        if template is None:
            raise HTTPException(
                status_code=409,
                detail="Interview template is unavailable.",
            )
        phase_slug = str(row["current_phase"])
        phase_index = next(
            (
                index
                for index, phase in enumerate(template.phases)
                if phase.slug == phase_slug
            ),
            None,
        )
        if phase_index is None:
            raise HTTPException(
                status_code=409,
                detail="Interview phase is not recognized.",
            )
        phase = template.phases[phase_index]
        evidence = evaluate_response(phase, request.content)
        _insert_message(
            connection,
            session_id=session_id,
            role="candidate",
            phase=phase.slug,
            content=request.content.strip(),
            evidence={
                "idempotency_key": idempotency_key,
                "label": evidence.label,
                "score": evidence.score,
                "concept_coverage": evidence.concept_coverage,
                "depth_score": evidence.depth_score,
                "matched_concepts": list(evidence.matched_concepts),
                "missing_concepts": list(evidence.missing_concepts),
                "word_count": evidence.word_count,
                "rubric": _EVALUATOR_VERSION,
            },
        )

        next_index = phase_index + 1
        if next_index < len(template.phases):
            next_phase = template.phases[next_index]
            connection.execute(
                text(
                    """
                    UPDATE mock_interview_sessions
                    SET current_phase=:current_phase,
                        updated_at=CURRENT_TIMESTAMP
                    WHERE id=:session_id
                    """
                ),
                {
                    "current_phase": next_phase.slug,
                    "session_id": session_id,
                },
            )
            _insert_message(
                connection,
                session_id=session_id,
                role="interviewer",
                phase=next_phase.slug,
                content=next_phase.prompt,
                evidence={
                    "template": template.slug,
                    "label": next_phase.label,
                    "rubric": _EVALUATOR_VERSION,
                },
            )
        else:
            _complete_session(
                connection,
                session_id=session_id,
                organization_id=principal.organization_id,
                focus=focus,
            )
        return _detail(connection, session_id)


@router.post(
    "/{session_id}/actions",
    response_model=MockInterviewSessionView,
)
def update_mock_interview_state(
    session_id: UUID,
    request: MockInterviewActionInput,
    principal: MockWritePrincipal,
    engine: DatabaseEngine,
) -> MockInterviewSessionView:
    with principal_transaction(engine, principal) as connection:
        row = _session_row(connection, session_id, lock=True)
        current = MockInterviewState(str(row["status"]))
        transitions = {
            ("pause", MockInterviewState.in_progress): MockInterviewState.paused,
            ("resume", MockInterviewState.paused): MockInterviewState.in_progress,
            ("cancel", MockInterviewState.in_progress): MockInterviewState.cancelled,
            ("cancel", MockInterviewState.paused): MockInterviewState.cancelled,
        }
        target = transitions.get((request.action, current))
        if target is None:
            raise HTTPException(
                status_code=409,
                detail="Requested mock interview state transition is invalid.",
            )
        connection.execute(
            text(
                f"""
                UPDATE mock_interview_sessions
                SET status=CAST(:status AS mock_interview_state),
                    updated_at=CURRENT_TIMESTAMP
                WHERE id=:session_id
                  AND candidate_id={_CURRENT_USER_SQL}
                """
            ),
            {"status": target.value, "session_id": session_id},
        )
        return _detail(connection, session_id)
