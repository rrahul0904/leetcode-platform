from __future__ import annotations

import json
from hashlib import sha256
from typing import Annotated, Any, cast
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import Connection, text

from .auth import require_permissions
from .database import DatabaseEngine, principal_transaction
from .execution import (
    ExecutionLimits,
    LocalFunctionalPythonRunner,
)
from .execution import (
    ExecutionResult as RunnerExecutionResult,
)
from .practice import (
    PracticeSessionNotFoundError,
    PracticeSessionRepository,
    candidate_id,
    published_question_payload,
    question_tests,
)
from .schemas import (
    AuthenticatedPrincipal,
    CandidateEvidence,
    CandidateReadiness,
    CandidateSubmission,
    CompetencyReadiness,
    ExecutionResult,
    ExecutionState,
    ExecutionTestResult,
    NextAction,
    PracticeRunRequest,
    PracticeSessionEventInput,
    PracticeSessionState,
    PracticeSubmitRequest,
    ReadinessSummary,
    SubmissionEvaluationRecord,
    SubmissionRuntime,
    SubmissionStatus,
)

router = APIRouter(prefix="/api/v1", tags=["submissions"])

EVALUATOR_VERSION = "deterministic-python-v1"
READINESS_VERSION = "weighted-evidence-v1"
RUNNER = LocalFunctionalPythonRunner()

CandidateWritePrincipal = Annotated[
    AuthenticatedPrincipal,
    Depends(require_permissions("submission:create")),
]
CandidateReadPrincipal = Annotated[
    AuthenticatedPrincipal,
    Depends(require_permissions("submission:read-own")),
]


def deterministic_evaluation(result: RunnerExecutionResult) -> dict[str, Any]:
    public_total = len(result.public_results)
    public_passed = sum(item.passed for item in result.public_results)
    hidden_total = result.hidden_summary.total
    hidden_passed = result.hidden_summary.passed
    total = public_total + hidden_total
    passed = public_passed + hidden_passed
    correctness = passed / total if total else 0.0
    testing = public_passed / public_total if public_total else correctness
    robustness = hidden_passed / hidden_total if hidden_total else correctness
    quality = result.quality_signals
    code_quality = (
        0.55 * float(bool(quality.get("syntax_valid")))
        + 0.20 * float(not bool(quality.get("contains_todo")))
        + 0.15 * float(int(str(quality.get("debug_print_count", 0))) <= 1)
        + 0.10 * float(int(str(quality.get("function_count", 0))) >= 1)
    )
    complexity = 1.0 if result.status == "passed" else (0.5 if result.status == "failed" else 0.0)
    overall = (
        0.60 * correctness
        + 0.15 * code_quality
        + 0.10 * complexity
        + 0.10 * robustness
        + 0.05 * testing
    )
    return {
        "correctness_score": round(correctness, 5),
        "complexity_score": round(complexity, 5),
        "code_quality_score": round(code_quality, 5),
        "testing_score": round(testing, 5),
        "robustness_score": round(robustness, 5),
        "overall_score": round(overall, 5),
        "evaluator_version": EVALUATOR_VERSION,
        "deterministic_signals": {
            "public_total": public_total,
            "public_passed": public_passed,
            "hidden_total": hidden_total,
            "hidden_passed": hidden_passed,
            "execution_status": result.status,
        },
        "heuristic_signals": {
            "source_quality": quality,
            "disclaimer": "Static source-quality signals are advisory and separately labeled.",
        },
    }


def _execution_state(status: str) -> ExecutionState:
    if status == "passed":
        return ExecutionState.passed
    if status == "failed":
        return ExecutionState.failed
    return ExecutionState.error


def _submission_status(status: str) -> SubmissionStatus:
    if status == "passed":
        return SubmissionStatus.passed
    if status == "failed":
        return SubmissionStatus.failed
    return SubmissionStatus.error


def _api_execution(
    request_id: UUID,
    submission_id: UUID | None,
    result: RunnerExecutionResult,
) -> ExecutionResult:
    return ExecutionResult(
        execution_request_id=request_id,
        submission_id=submission_id,
        state=_execution_state(result.status),
        public_results=[
            ExecutionTestResult(
                test_id=item.id,
                name=item.name,
                passed=item.passed,
                expected=item.expected_output,
                actual=item.actual_output,
            )
            for item in result.public_results
        ],
        hidden_total=result.hidden_summary.total,
        hidden_passed=result.hidden_summary.passed,
        runtime_ms=result.duration_ms,
        memory_kb=result.memory_kb,
        error_category=result.error_category,
        candidate_message=result.candidate_message,
        quality_signals=result.quality_signals,
    )


def _session_question(
    connection: Connection,
    session_id: UUID,
    slug: str,
) -> dict[str, Any]:
    row = (
        connection.execute(
            text(
                """
                SELECT ps.id, ps.state, ps.question_version_id, q.slug
                FROM practice_sessions ps
                JOIN question_versions v ON v.id=ps.question_version_id
                JOIN questions q ON q.id=v.question_id
                WHERE ps.id=:session_id AND q.slug=:slug
                """
            ),
            {"session_id": session_id, "slug": slug},
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        raise PracticeSessionNotFoundError
    return published_question_payload(connection, slug)


def _insert_execution_request(
    connection: Connection,
    principal: AuthenticatedPrincipal,
    *,
    session_id: UUID,
    submission_id: UUID | None,
    question_version_id: UUID,
    source_code: str,
    idempotency_key: str,
) -> UUID:
    limits = ExecutionLimits()
    request_id = connection.execute(
        text(
            """
            INSERT INTO execution_requests (
                organization_id, candidate_id, practice_session_id, submission_id,
                question_version_id, runtime, adapter, state, idempotency_key,
                source_hash, limits, started_at
            ) VALUES (
                CAST(NULLIF(:organization_id, '') AS uuid),
                NULLIF(current_setting('rigor.user_id', true), '')::uuid,
                :session_id, :submission_id, :question_version_id,
                'python3.13', :adapter, 'RUNNING'::execution_state,
                :idempotency_key, :source_hash, CAST(:limits AS jsonb),
                CURRENT_TIMESTAMP
            )
            RETURNING id
            """
        ),
        {
            "organization_id": principal.organization_id or "",
            "session_id": session_id,
            "submission_id": submission_id,
            "question_version_id": question_version_id,
            "adapter": RUNNER.adapter_name,
            "idempotency_key": idempotency_key,
            "source_hash": sha256(source_code.encode()).hexdigest(),
            "limits": json.dumps(
                {
                    "timeout_ms": limits.timeout_ms,
                    "memory_mb": limits.memory_mb,
                    "output_bytes": limits.output_bytes,
                }
            ),
        },
    ).scalar_one()
    return UUID(str(request_id))


def _complete_execution_request(
    connection: Connection,
    request_id: UUID,
    result: RunnerExecutionResult,
) -> None:
    state = _execution_state(result.status).value
    connection.execute(
        text(
            """
            UPDATE execution_requests
            SET state=CAST(:state AS execution_state), completed_at=CURRENT_TIMESTAMP
            WHERE id=:request_id
            """
        ),
        {"request_id": request_id, "state": state},
    )
    connection.execute(
        text(
            """
            INSERT INTO execution_events (
                execution_request_id, sequence_number, state, details
            ) VALUES (
                :request_id, 1, CAST(:state AS execution_state), CAST(:details AS jsonb)
            )
            """
        ),
        {
            "request_id": request_id,
            "state": state,
            "details": json.dumps(
                {
                    "duration_ms": result.duration_ms,
                    "error_category": result.error_category,
                }
            ),
        },
    )


@router.post("/questions/{slug}/run", response_model=ExecutionResult)
def run_question(
    slug: str,
    request: PracticeRunRequest,
    principal: CandidateWritePrincipal,
    engine: DatabaseEngine,
) -> ExecutionResult:
    try:
        with principal_transaction(engine, principal) as connection:
            question = _session_question(connection, request.session_id, slug)
            tests = question_tests(question, public_only=True)
            request_id = _insert_execution_request(
                connection,
                principal,
                session_id=request.session_id,
                submission_id=None,
                question_version_id=UUID(str(question["question_version_id"])),
                source_code=request.source_code,
                idempotency_key=f"run:{uuid4()}",
            )
            result = RUNNER.execute(
                SubmissionRuntime.python,
                request.source_code,
                tests,
                limits=ExecutionLimits(),
            )
            _complete_execution_request(connection, request_id, result)
            connection.execute(
                text(
                    """
                    UPDATE practice_sessions
                    SET draft_code=:source, run_count=run_count + 1,
                        last_activity_at=CURRENT_TIMESTAMP, updated_at=CURRENT_TIMESTAMP
                    WHERE id=:session_id
                    """
                ),
                {"source": request.source_code, "session_id": request.session_id},
            )
            PracticeSessionRepository(connection).append_event(
                request.session_id,
                PracticeSessionEventInput(
                    event_type="CODE_RUN",
                    payload={"state": result.status, "duration_ms": result.duration_ms},
                ),
            )
            return _api_execution(request_id, None, result)
    except PracticeSessionNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail="Practice session or question not found.",
        ) from exc


def _persist_result(
    connection: Connection,
    submission_id: UUID,
    result: RunnerExecutionResult,
    evaluation: dict[str, Any],
) -> None:
    state = _execution_state(result.status).value
    status = _submission_status(result.status).value
    public = [item.model_dump(mode="json") for item in result.public_results]
    hidden = result.hidden_summary.model_dump(mode="json")
    connection.execute(
        text(
            """
            UPDATE submissions
            SET status=:status, public_test_results=CAST(:public AS jsonb),
                hidden_test_summary=CAST(:hidden AS jsonb),
                error_category=:error_category,
                execution_duration_ms=:duration_ms,
                completed_at=CURRENT_TIMESTAMP
            WHERE id=:submission_id
            """
        ),
        {
            "submission_id": submission_id,
            "status": status,
            "public": json.dumps(public),
            "hidden": json.dumps(hidden),
            "error_category": result.error_category,
            "duration_ms": result.duration_ms,
        },
    )
    connection.execute(
        text(
            """
            INSERT INTO submission_results (
                submission_id, status, public_results, hidden_total,
                hidden_passed, runtime_ms, memory_kb, error_category,
                candidate_message, quality_signals
            ) VALUES (
                :submission_id, CAST(:state AS execution_state),
                CAST(:public AS jsonb), :hidden_total, :hidden_passed,
                :duration_ms, :memory_kb, :error_category,
                :candidate_message, CAST(:quality_signals AS jsonb)
            )
            """
        ),
        {
            "submission_id": submission_id,
            "state": state,
            "public": json.dumps(public),
            "hidden_total": result.hidden_summary.total,
            "hidden_passed": result.hidden_summary.passed,
            "duration_ms": result.duration_ms,
            "memory_kb": result.memory_kb,
            "error_category": result.error_category,
            "candidate_message": result.candidate_message,
            "quality_signals": json.dumps(result.quality_signals),
        },
    )
    connection.execute(
        text(
            """
            INSERT INTO submission_evaluations (
                submission_id, correctness_score, complexity_score,
                code_quality_score, testing_score, robustness_score,
                overall_score, evaluator_version, deterministic_signals,
                heuristic_signals
            ) VALUES (
                :submission_id, :correctness_score, :complexity_score,
                :code_quality_score, :testing_score, :robustness_score,
                :overall_score, :evaluator_version,
                CAST(:deterministic_signals AS jsonb),
                CAST(:heuristic_signals AS jsonb)
            )
            """
        ),
        {
            "submission_id": submission_id,
            **{
                key: value
                for key, value in evaluation.items()
                if key not in {"deterministic_signals", "heuristic_signals"}
            },
            "deterministic_signals": json.dumps(evaluation["deterministic_signals"]),
            "heuristic_signals": json.dumps(evaluation["heuristic_signals"]),
        },
    )


def _write_evidence(
    connection: Connection,
    principal: AuthenticatedPrincipal,
    question_version_id: UUID,
    submission_id: UUID,
    evaluation: dict[str, Any],
) -> None:
    mappings = (
        connection.execute(
            text(
                """
                SELECT qc.competency_id, qc.confidence, qc.is_primary
                FROM question_versions v
                JOIN question_competencies qc ON qc.question_id=v.question_id
                WHERE v.id=:question_version_id
                """
            ),
            {"question_version_id": question_version_id},
        )
        .mappings()
        .all()
    )
    user_id = candidate_id(connection)
    for mapping in mappings:
        weight = float(mapping["confidence"]) * (1.0 if mapping["is_primary"] else 0.75)
        confidence = min(
            0.95,
            0.45
            + 0.05 * int(evaluation["deterministic_signals"]["public_total"])
            + 0.07 * int(evaluation["deterministic_signals"]["hidden_total"]),
        )
        connection.execute(
            text(
                """
                INSERT INTO candidate_competency_evidence (
                    organization_id, candidate_id, competency_id, source_type,
                    source_id, score, confidence, weight, evaluator_version,
                    observed_at, evidence
                ) VALUES (
                    CAST(NULLIF(:organization_id, '') AS uuid), :candidate_id,
                    :competency_id, 'CODING_SUBMISSION', :source_id, :score,
                    :confidence, :weight, :evaluator_version,
                    CURRENT_TIMESTAMP, CAST(:evidence AS jsonb)
                )
                """
            ),
            {
                "organization_id": principal.organization_id or "",
                "candidate_id": user_id,
                "competency_id": mapping["competency_id"],
                "source_id": str(submission_id),
                "score": evaluation["overall_score"],
                "confidence": confidence,
                "weight": weight,
                "evaluator_version": EVALUATOR_VERSION,
                "evidence": json.dumps(
                    {
                        "submission_id": str(submission_id),
                        "evaluation": evaluation["deterministic_signals"],
                    }
                ),
            },
        )
        aggregate = (
            connection.execute(
                text(
                    """
                    SELECT sum(score * confidence * weight)
                               / NULLIF(sum(confidence * weight), 0) AS mastery,
                           1 - exp(-sum(confidence * weight) / 3.0) AS confidence,
                           count(*) AS evidence_count,
                           max(observed_at) AS last_evidence_at
                    FROM candidate_competency_evidence
                    WHERE candidate_id=:candidate_id
                      AND competency_id=:competency_id
                    """
                ),
                {
                    "candidate_id": user_id,
                    "competency_id": mapping["competency_id"],
                },
            )
            .mappings()
            .one()
        )
        connection.execute(
            text(
                """
                INSERT INTO candidate_competency_mastery (
                    organization_id, candidate_id, competency_id, mastery,
                    confidence, evidence_count, last_evidence_at,
                    calculation_version
                ) VALUES (
                    CAST(NULLIF(:organization_id, '') AS uuid), :candidate_id,
                    :competency_id, :mastery, :confidence, :evidence_count,
                    :last_evidence_at, :calculation_version
                )
                ON CONFLICT (candidate_id, competency_id) DO UPDATE
                SET mastery=EXCLUDED.mastery, confidence=EXCLUDED.confidence,
                    evidence_count=EXCLUDED.evidence_count,
                    last_evidence_at=EXCLUDED.last_evidence_at,
                    calculation_version=EXCLUDED.calculation_version,
                    updated_at=CURRENT_TIMESTAMP
                """
            ),
            {
                "organization_id": principal.organization_id or "",
                "candidate_id": user_id,
                "competency_id": mapping["competency_id"],
                "mastery": aggregate["mastery"],
                "confidence": aggregate["confidence"],
                "evidence_count": aggregate["evidence_count"],
                "last_evidence_at": aggregate["last_evidence_at"],
                "calculation_version": READINESS_VERSION,
            },
        )


def _mastery_rows(connection: Connection) -> list[dict[str, Any]]:
    rows = (
        connection.execute(
            text(
                """
                SELECT c.id AS competency_id, c.slug, c.name,
                       COALESCE(m.mastery, 0) AS score,
                       COALESCE(m.confidence, 0) AS confidence,
                       COALESCE(m.evidence_count, 0) AS evidence_count,
                       m.last_evidence_at AS last_observed_at
                FROM competencies c
                LEFT JOIN candidate_competency_mastery m
                  ON m.competency_id=c.id
                 AND m.candidate_id=NULLIF(
                    current_setting('rigor.user_id', true), ''
                 )::uuid
                WHERE m.id IS NOT NULL
                ORDER BY m.mastery DESC, c.slug
                """
            )
        )
        .mappings()
        .all()
    )
    return [dict(row) for row in rows]


def _readiness(connection: Connection) -> CandidateReadiness:
    rows = _mastery_rows(connection)
    competencies = [
        CompetencyReadiness(
            **row,
            trend="insufficient_evidence" if int(row["evidence_count"]) < 2 else "stable",
        )
        for row in rows
    ]
    weights = connection.execute(
        text(
            """
            SELECT competency_weights
            FROM role_readiness_profiles
            WHERE slug='STAFF_AI_ENGINEER' AND active
            """
        )
    ).scalar_one()
    typed_weights = (
        {
            str(key): float(str(value))
            for key, value in cast(dict[object, object], weights).items()
        }
        if isinstance(weights, dict)
        else {}
    )
    total_weight = sum(float(typed_weights.get(item.slug, 0.02)) for item in competencies)
    score = (
        sum(item.score * float(typed_weights.get(item.slug, 0.02)) for item in competencies)
        / total_weight
        if total_weight
        else 0.0
    )
    confidence = (
        sum(item.confidence * float(typed_weights.get(item.slug, 0.02)) for item in competencies)
        / total_weight
        if total_weight
        else 0.0
    )
    calculated_at = connection.execute(text("SELECT CURRENT_TIMESTAMP")).scalar_one()
    return CandidateReadiness(
        target_role="Staff AI Engineer",
        overall=ReadinessSummary(score=round(score, 5), confidence=round(confidence, 5)),
        evidence_count=sum(item.evidence_count for item in competencies),
        competencies=competencies,
        critical_gaps=sorted(competencies, key=lambda item: item.score)[:3],
        strongest_areas=competencies[:3],
        calculated_at=calculated_at,
    )


def _snapshot_readiness(
    connection: Connection,
    principal: AuthenticatedPrincipal,
) -> CandidateReadiness:
    readiness = _readiness(connection)
    connection.execute(
        text(
            """
            INSERT INTO readiness_snapshots (
                organization_id, candidate_id, overall_readiness, confidence,
                evidence_count, competency_readiness, role_readiness,
                current_risks, recommended_actions, calculation_version,
                calculated_at
            ) VALUES (
                CAST(NULLIF(:organization_id, '') AS uuid),
                NULLIF(current_setting('rigor.user_id', true), '')::uuid,
                :score, :confidence, :evidence_count,
                CAST(:competencies AS jsonb), CAST(:role AS jsonb),
                CAST(:risks AS jsonb), '[]'::jsonb, :version,
                CURRENT_TIMESTAMP
            )
            """
        ),
        {
            "organization_id": principal.organization_id or "",
            "score": readiness.overall.score,
            "confidence": readiness.overall.confidence,
            "evidence_count": readiness.evidence_count,
            "competencies": json.dumps(
                [item.model_dump(mode="json") for item in readiness.competencies]
            ),
            "role": json.dumps(
                {
                    "target_role": readiness.target_role,
                    "score": readiness.overall.score,
                    "confidence": readiness.overall.confidence,
                }
            ),
            "risks": json.dumps(
                [f"Low evidence for {item.name}" for item in readiness.critical_gaps]
            ),
            "version": READINESS_VERSION,
        },
    )
    return readiness


def _next_action(connection: Connection, readiness: CandidateReadiness) -> NextAction:
    weakest = readiness.critical_gaps[0] if readiness.critical_gaps else None
    row = (
        connection.execute(
            text(
                """
                SELECT q.slug, v.title, c.slug AS competency_slug
                FROM questions q
                JOIN question_versions v ON v.id=q.current_published_version_id
                LEFT JOIN question_competencies qc ON qc.question_id=q.id
                LEFT JOIN competencies c ON c.id=qc.competency_id
                WHERE v.state='published'::content_state
                  AND v.structured_content->'mode_specification'
                      ->>'starter_code' LIKE 'def %'
                  AND (
                    CAST(:competency_slug AS text) IS NULL
                    OR c.slug=CAST(:competency_slug AS text)
                  )
                ORDER BY COALESCE(qc.is_primary, false) DESC, q.slug
                LIMIT 1
                """
            ),
            {"competency_slug": weakest.slug if weakest else None},
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="No published practice question is available.")
    reason = (
        f"Build evidence in {weakest.name}, currently your lowest measured competency."
        if weakest
        else "Complete a first practice session to establish an evidence baseline."
    )
    return NextAction(
        type="PRACTICE",
        source_id=str(row["slug"]),
        title=str(row["title"]),
        href=f"/practice/{row['slug']}",
        reasons=[reason],
        competency_slug=str(row["competency_slug"]) if row["competency_slug"] else None,
    )


@router.post("/questions/{slug}/submissions", response_model=CandidateSubmission, status_code=201)
def submit_question(
    slug: str,
    request: PracticeSubmitRequest,
    principal: CandidateWritePrincipal,
    engine: DatabaseEngine,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=8, max_length=160)],
) -> CandidateSubmission:
    try:
        with principal_transaction(engine, principal) as connection:
            existing = connection.execute(
                text(
                    """
                    SELECT id FROM submissions
                    WHERE candidate_id=NULLIF(
                        current_setting('rigor.user_id', true), ''
                    )::uuid
                      AND idempotency_key=:idempotency_key
                    """
                ),
                {"idempotency_key": idempotency_key},
            ).scalar_one_or_none()
            if existing is not None:
                return _submission(connection, UUID(str(existing)))
            question = _session_question(connection, request.session_id, slug)
            question_version_id = UUID(str(question["question_version_id"]))
            submission_id = UUID(
                str(
                    connection.execute(
                        text(
                            """
                            INSERT INTO submissions (
                                organization_id, candidate_id, practice_session_id,
                                question_version_id, runtime, submitted_source,
                                status, idempotency_key, started_at
                            ) VALUES (
                                CAST(NULLIF(:organization_id, '') AS uuid),
                                NULLIF(current_setting('rigor.user_id', true), '')::uuid,
                                :session_id, :question_version_id, :runtime,
                                :source, 'running', :idempotency_key,
                                CURRENT_TIMESTAMP
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
            request_id = _insert_execution_request(
                connection,
                principal,
                session_id=request.session_id,
                submission_id=submission_id,
                question_version_id=question_version_id,
                source_code=request.source_code,
                idempotency_key=f"submit:{idempotency_key}",
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
            result = RUNNER.execute(
                request.runtime,
                request.source_code,
                question_tests(question, public_only=False),
                limits=ExecutionLimits(),
            )
            _complete_execution_request(connection, request_id, result)
            evaluation = deterministic_evaluation(result)
            _persist_result(connection, submission_id, result, evaluation)
            _write_evidence(
                connection,
                principal,
                question_version_id,
                submission_id,
                evaluation,
            )
            connection.execute(
                text(
                    """
                    UPDATE practice_sessions
                    SET draft_code=:source, state='COMPLETED'::practice_session_state,
                        submission_count=submission_count + 1,
                        completed_at=CURRENT_TIMESTAMP,
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
                    event_type="EVALUATION_COMPLETED",
                    payload={
                        "submission_id": str(submission_id),
                        "overall_score": evaluation["overall_score"],
                    },
                ),
            )
            _snapshot_readiness(connection, principal)
            return _submission(connection, submission_id, request_id=request_id)
    except PracticeSessionNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail="Practice session or question not found.",
        ) from exc


def _submission(
    connection: Connection,
    submission_id: UUID,
    *,
    request_id: UUID | None = None,
) -> CandidateSubmission:
    row = (
        connection.execute(
            text(
                """
                SELECT s.id, s.practice_session_id, s.question_version_id,
                       q.slug AS question_slug, v.title AS question_title,
                       v.version AS publication_version, s.runtime,
                       s.submitted_source AS source_code, s.status,
                       s.created_at AS submitted_at, s.completed_at,
                       er.id AS execution_request_id, sr.status AS execution_state,
                       sr.public_results, sr.hidden_total, sr.hidden_passed,
                       sr.runtime_ms, sr.memory_kb, sr.error_category,
                       sr.candidate_message, sr.quality_signals,
                       se.correctness_score, se.complexity_score,
                       se.code_quality_score, se.testing_score,
                       se.robustness_score, se.overall_score,
                       se.evaluator_version, se.deterministic_signals,
                       se.heuristic_signals, se.created_at AS evaluated_at
                FROM submissions s
                JOIN question_versions v ON v.id=s.question_version_id
                JOIN questions q ON q.id=v.question_id
                JOIN submission_results sr ON sr.submission_id=s.id
                JOIN submission_evaluations se ON se.submission_id=s.id
                LEFT JOIN execution_requests er ON er.submission_id=s.id
                WHERE s.id=:submission_id
                ORDER BY er.created_at DESC
                LIMIT 1
                """
            ),
            {"submission_id": submission_id},
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Submission not found.")
    data = dict(row)
    execution_id = request_id or UUID(str(data["execution_request_id"]))
    public_objects = (
        cast(list[object], data["public_results"])
        if isinstance(data["public_results"], list)
        else []
    )
    public = [cast(dict[str, object], item) for item in public_objects if isinstance(item, dict)]
    return CandidateSubmission(
        id=UUID(str(data["id"])),
        practice_session_id=UUID(str(data["practice_session_id"])),
        question_version_id=UUID(str(data["question_version_id"])),
        question_slug=str(data["question_slug"]),
        question_title=str(data["question_title"]),
        publication_version=str(data["publication_version"]),
        runtime=SubmissionRuntime(str(data["runtime"])),
        source_code=str(data["source_code"]),
        status=SubmissionStatus(str(data["status"])),
        execution=ExecutionResult(
            execution_request_id=execution_id,
            submission_id=UUID(str(data["id"])),
            state=ExecutionState(str(data["execution_state"])),
            public_results=[
                ExecutionTestResult(
                    test_id=str(item.get("id", "")),
                    name=str(item.get("name", "")),
                    passed=bool(item.get("passed")),
                    expected=item.get("expected_output"),
                    actual=item.get("actual_output"),
                )
                for item in public
            ],
            hidden_total=int(data["hidden_total"]),
            hidden_passed=int(data["hidden_passed"]),
            runtime_ms=data["runtime_ms"],
            memory_kb=data["memory_kb"],
            error_category=data["error_category"],
            candidate_message=data["candidate_message"],
            quality_signals=data["quality_signals"],
        ),
        evaluation=SubmissionEvaluationRecord(
            correctness_score=float(data["correctness_score"]),
            complexity_score=float(data["complexity_score"]),
            code_quality_score=float(data["code_quality_score"]),
            testing_score=float(data["testing_score"]),
            robustness_score=float(data["robustness_score"]),
            overall_score=float(data["overall_score"]),
            evaluator_version=str(data["evaluator_version"]),
            deterministic_signals=data["deterministic_signals"],
            heuristic_signals=data["heuristic_signals"],
            created_at=data["evaluated_at"],
        ),
        submitted_at=data["submitted_at"],
        completed_at=data["completed_at"],
    )


@router.get("/submissions", response_model=list[CandidateSubmission])
def list_submissions(
    principal: CandidateReadPrincipal,
    engine: DatabaseEngine,
) -> list[CandidateSubmission]:
    with principal_transaction(engine, principal) as connection:
        ids = connection.execute(
            text("SELECT id FROM submissions ORDER BY created_at DESC LIMIT 100")
        ).scalars()
        return [_submission(connection, UUID(str(value))) for value in ids]


@router.get("/submissions/{submission_id}", response_model=CandidateSubmission)
def get_submission(
    submission_id: UUID,
    principal: CandidateReadPrincipal,
    engine: DatabaseEngine,
) -> CandidateSubmission:
    with principal_transaction(engine, principal) as connection:
        return _submission(connection, submission_id)


@router.get(
    "/practice-sessions/{session_id}/submissions",
    response_model=list[CandidateSubmission],
)
def list_session_submissions(
    session_id: UUID,
    principal: CandidateReadPrincipal,
    engine: DatabaseEngine,
) -> list[CandidateSubmission]:
    with principal_transaction(engine, principal) as connection:
        PracticeSessionRepository(connection).get(session_id)
        ids = connection.execute(
            text(
                """
                SELECT id FROM submissions
                WHERE practice_session_id=:session_id
                ORDER BY created_at DESC
                """
            ),
            {"session_id": session_id},
        ).scalars()
        return [_submission(connection, UUID(str(value))) for value in ids]


@router.get("/me/evidence", response_model=list[CandidateEvidence])
def candidate_evidence(
    principal: CandidateReadPrincipal,
    engine: DatabaseEngine,
) -> list[CandidateEvidence]:
    with principal_transaction(engine, principal) as connection:
        rows = (
            connection.execute(
                text(
                    """
                    SELECT e.id, e.competency_id, c.slug AS competency_slug,
                           c.name AS competency_name, e.source_type, e.source_id,
                           e.score, e.confidence, e.weight,
                           e.evaluator_version, e.evidence AS metadata,
                           e.observed_at
                    FROM candidate_competency_evidence e
                    JOIN competencies c ON c.id=e.competency_id
                    ORDER BY e.observed_at DESC
                    """
                )
            )
            .mappings()
            .all()
        )
        return [CandidateEvidence.model_validate(dict(row)) for row in rows]


@router.get("/me/competencies", response_model=list[CompetencyReadiness])
def candidate_competencies(
    principal: CandidateReadPrincipal,
    engine: DatabaseEngine,
) -> list[CompetencyReadiness]:
    with principal_transaction(engine, principal) as connection:
        return _readiness(connection).competencies


@router.get("/me/readiness", response_model=CandidateReadiness)
def candidate_readiness(
    principal: CandidateReadPrincipal,
    engine: DatabaseEngine,
) -> CandidateReadiness:
    with principal_transaction(engine, principal) as connection:
        return _readiness(connection)


@router.get("/me/next-action", response_model=NextAction)
def next_action(
    principal: CandidateReadPrincipal,
    engine: DatabaseEngine,
) -> NextAction:
    with principal_transaction(engine, principal) as connection:
        recommendation = _next_action(connection, _readiness(connection))
        connection.execute(
            text(
                """
                INSERT INTO recommendation_events (
                    organization_id, candidate_id, recommendation_type,
                    source_type, source_id, title, reason, rank, status,
                    recommended_at, context
                ) VALUES (
                    CAST(NULLIF(:organization_id, '') AS uuid),
                    NULLIF(current_setting('rigor.user_id', true), '')::uuid,
                    :type, 'HOSTED_QUESTION', :source_id, :title, :reason,
                    1, 'SHOWN', CURRENT_TIMESTAMP, CAST(:context AS jsonb)
                )
                """
            ),
            {
                "organization_id": principal.organization_id or "",
                "type": recommendation.type,
                "source_id": recommendation.source_id,
                "title": recommendation.title,
                "reason": recommendation.reasons[0],
                "context": json.dumps({"competency_slug": recommendation.competency_slug}),
            },
        )
        return recommendation
