from __future__ import annotations

import json
from typing import Any

from sqlalchemy import Connection, text

from .execution import source_quality_signals
from .execution_domain import ExecutionStatus
from .execution_results import DispatchPackage, TrustedExecutionProjection

EVALUATOR_VERSION = "deterministic-python-async-v1"


def _legacy_status(projection: TrustedExecutionProjection) -> tuple[str, str]:
    if projection.execution_status is ExecutionStatus.completed:
        if projection.all_tests_passed:
            return "passed", "PASSED"
        return "failed", "FAILED"
    return "error", "ERROR"


def _evaluation(
    package: DispatchPackage,
    projection: TrustedExecutionProjection,
) -> dict[str, Any]:
    public_total = len(projection.public_results)
    public_passed = sum(bool(item["passed"]) for item in projection.public_results)
    hidden_total = projection.hidden_total
    hidden_passed = projection.hidden_passed
    total = public_total + hidden_total
    passed = public_passed + hidden_passed
    correctness = passed / total if total else 0.0
    testing = public_passed / public_total if public_total else correctness
    robustness = hidden_passed / hidden_total if hidden_total else correctness
    quality = source_quality_signals(package.source_code)
    code_quality = (
        0.55 * float(bool(quality.get("syntax_valid")))
        + 0.20 * float(not bool(quality.get("contains_todo")))
        + 0.15 * float(int(str(quality.get("debug_print_count", 0))) <= 1)
        + 0.10 * float(int(str(quality.get("function_count", 0))) >= 1)
    )
    submission_status, _ = _legacy_status(projection)
    if submission_status == "passed":
        complexity = 1.0
    elif submission_status == "failed":
        complexity = 0.5
    else:
        complexity = 0.0
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
            "execution_status": projection.execution_status.value,
        },
        "heuristic_signals": {
            "source_quality": quality,
            "disclaimer": "Static source-quality signals are advisory and separately labeled.",
        },
    }


def finalize_submission(
    connection: Connection,
    *,
    package: DispatchPackage,
    projection: TrustedExecutionProjection,
) -> None:
    if package.submission_id is None or package.execution_type != "SUBMIT":
        return

    existing = connection.execute(
        text("SELECT 1 FROM submission_results WHERE submission_id=:submission_id"),
        {"submission_id": package.submission_id},
    ).scalar_one_or_none()
    if existing is not None:
        return

    submission_status, execution_state = _legacy_status(projection)
    public_results = [
        {
            "id": str(item["test_id"]),
            "name": str(item["name"]),
            "passed": bool(item["passed"]),
            "expected_output": item.get("expected"),
            "actual_output": item.get("actual"),
            "error_category": item.get("error_category"),
        }
        for item in projection.public_results
    ]
    quality = source_quality_signals(package.source_code)
    evaluation = _evaluation(package, projection)

    connection.execute(
        text(
            """
            UPDATE submissions
            SET status=:status,
                public_test_results=CAST(:public AS jsonb),
                hidden_test_summary=CAST(:hidden AS jsonb),
                error_category=:error_category,
                execution_duration_ms=:duration_ms,
                started_at=COALESCE(started_at, CURRENT_TIMESTAMP),
                completed_at=CURRENT_TIMESTAMP
            WHERE id=:submission_id
            """
        ),
        {
            "submission_id": package.submission_id,
            "status": submission_status,
            "public": json.dumps(public_results, separators=(",", ":")),
            "hidden": json.dumps(
                {"total": projection.hidden_total, "passed": projection.hidden_passed},
                separators=(",", ":"),
            ),
            "error_category": projection.error_category,
            "duration_ms": projection.runtime_ms,
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
                :duration_ms, NULL, :error_category,
                :candidate_message, CAST(:quality_signals AS jsonb)
            )
            """
        ),
        {
            "submission_id": package.submission_id,
            "state": execution_state,
            "public": json.dumps(public_results, separators=(",", ":")),
            "hidden_total": projection.hidden_total,
            "hidden_passed": projection.hidden_passed,
            "duration_ms": projection.runtime_ms,
            "error_category": projection.error_category,
            "candidate_message": projection.candidate_message,
            "quality_signals": json.dumps(quality, separators=(",", ":")),
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
            "submission_id": package.submission_id,
            **{
                key: value
                for key, value in evaluation.items()
                if key not in {"deterministic_signals", "heuristic_signals"}
            },
            "deterministic_signals": json.dumps(
                evaluation["deterministic_signals"], separators=(",", ":")
            ),
            "heuristic_signals": json.dumps(
                evaluation["heuristic_signals"], separators=(",", ":")
            ),
        },
    )

    updated = connection.execute(
        text(
            """
            UPDATE practice_sessions
            SET state='COMPLETED'::practice_session_state,
                completed_at=CURRENT_TIMESTAMP,
                last_activity_at=CURRENT_TIMESTAMP,
                updated_at=CURRENT_TIMESTAMP
            WHERE id=:session_id
              AND state IN (
                'SUBMITTED'::practice_session_state,
                'EVALUATING'::practice_session_state
              )
            RETURNING id
            """
        ),
        {"session_id": package.practice_session_id},
    ).scalar_one_or_none()
    if updated is not None:
        connection.execute(
            text(
                """
                INSERT INTO practice_session_events (
                    session_id, sequence_number, event_type, payload
                )
                SELECT :session_id,
                       COALESCE(max(sequence_number), 0) + 1,
                       'EVALUATION_COMPLETED',
                       CAST(:payload AS jsonb)
                FROM practice_session_events
                WHERE session_id=:session_id
                """
            ),
            {
                "session_id": package.practice_session_id,
                "payload": json.dumps(
                    {
                        "submission_id": str(package.submission_id),
                        "execution_id": str(package.execution_id),
                        "overall_score": evaluation["overall_score"],
                    },
                    separators=(",", ":"),
                ),
            },
        )
