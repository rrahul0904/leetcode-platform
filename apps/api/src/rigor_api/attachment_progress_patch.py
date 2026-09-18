"""Attach durable execution submissions to candidate competency progress.

The async execution plane already persists deterministic submission scores. This
patch adds the same competency-evidence/mastery projection used by the legacy
synchronous path so activating the durable Python/SQL routes does not regress
candidate progress.
"""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import Connection, text

from . import execution_submission
from .execution_results import DispatchPackage, TrustedExecutionProjection

_ORIGINAL_FINALIZE = execution_submission.finalize_submission
READINESS_VERSION = "weighted-evidence-v2-async"


def _write_progress(connection: Connection, package: DispatchPackage) -> None:
    if package.submission_id is None or package.execution_type != "SUBMIT":
        return
    existing = connection.execute(
        text(
            """
            SELECT 1
            FROM candidate_competency_evidence
            WHERE candidate_id=:candidate_id
              AND source_type='CODING_SUBMISSION'
              AND source_id=:source_id
            LIMIT 1
            """
        ),
        {"candidate_id": package.candidate_id, "source_id": str(package.submission_id)},
    ).scalar_one_or_none()
    if existing is not None:
        return
    evaluation = (
        connection.execute(
            text(
                """
                SELECT overall_score, evaluator_version, deterministic_signals
                FROM submission_evaluations
                WHERE submission_id=:submission_id
                ORDER BY created_at DESC
                LIMIT 1
                """
            ),
            {"submission_id": package.submission_id},
        )
        .mappings()
        .one_or_none()
    )
    if evaluation is None:
        return
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
            {"question_version_id": package.question_version_id},
        )
        .mappings()
        .all()
    )
    signals: dict[str, Any] = (
        dict(evaluation["deterministic_signals"])
        if isinstance(evaluation["deterministic_signals"], dict)
        else {}
    )
    public_total = int(signals.get("public_total") or 0)
    hidden_total = int(signals.get("hidden_total") or 0)
    evidence_confidence = min(0.95, 0.45 + 0.05 * public_total + 0.07 * hidden_total)
    for mapping in mappings:
        weight = float(mapping["confidence"]) * (1.0 if mapping["is_primary"] else 0.75)
        connection.execute(
            text(
                """
                INSERT INTO candidate_competency_evidence (
                    organization_id, candidate_id, competency_id, source_type,
                    source_id, score, confidence, weight, evaluator_version,
                    observed_at, evidence
                ) VALUES (
                    :organization_id, :candidate_id, :competency_id,
                    'CODING_SUBMISSION', :source_id, :score, :confidence,
                    :weight, :evaluator_version, CURRENT_TIMESTAMP,
                    CAST(:evidence AS jsonb)
                )
                """
            ),
            {
                "organization_id": package.organization_id,
                "candidate_id": package.candidate_id,
                "competency_id": mapping["competency_id"],
                "source_id": str(package.submission_id),
                "score": float(evaluation["overall_score"]),
                "confidence": evidence_confidence,
                "weight": weight,
                "evaluator_version": str(evaluation["evaluator_version"]),
                "evidence": json.dumps(
                    {
                        "submission_id": str(package.submission_id),
                        "execution_id": str(package.execution_id),
                        "runtime": package.runtime,
                        "deterministic_signals": signals,
                    },
                    separators=(",", ":"),
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
                    "candidate_id": package.candidate_id,
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
                    :organization_id, :candidate_id, :competency_id, :mastery,
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
                "organization_id": package.organization_id,
                "candidate_id": package.candidate_id,
                "competency_id": mapping["competency_id"],
                "mastery": aggregate["mastery"],
                "confidence": aggregate["confidence"],
                "evidence_count": aggregate["evidence_count"],
                "last_evidence_at": aggregate["last_evidence_at"],
                "version": READINESS_VERSION,
            },
        )


def finalize_submission(
    connection: Connection,
    *,
    package: DispatchPackage,
    projection: TrustedExecutionProjection,
) -> None:
    _ORIGINAL_FINALIZE(connection, package=package, projection=projection)
    _write_progress(connection, package)


execution_submission.finalize_submission = finalize_submission
