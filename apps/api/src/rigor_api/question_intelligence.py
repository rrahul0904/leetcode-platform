from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import Engine, text

from .persistence import audit_event, ensure_user
from .schemas import (
    AdminQuestionRecord,
    AuthenticatedPrincipal,
    CoverageGapRecord,
    DuplicateCandidateRecord,
    GapRecomputeResult,
    LicenseInventoryRecord,
    ProvenanceInventoryRecord,
    QuestionFamilyRecord,
    QuestionFreshnessRecord,
)


class QuestionIntelligenceRepository:
    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    def questions(self) -> list[AdminQuestionRecord]:
        with self.engine.connect() as connection:
            rows = (
                connection.execute(
                    text(
                        """
                        SELECT q.id AS question_id, q.external_id, q.slug, q.record_type,
                               q.visibility, v.id AS version_id, v.version, v.title,
                               t.slug AS primary_track, v.difficulty,
                               v.expected_seniority AS role_level, v.state::text AS state,
                               v.source_revision, v.updated_at,
                               q.current_published_version_id=v.id AS is_current_published
                        FROM questions q
                        JOIN question_tracks t ON t.id=q.primary_track_id
                        JOIN LATERAL (
                            SELECT * FROM question_versions candidate
                            WHERE candidate.question_id=q.id
                            ORDER BY candidate.created_at DESC LIMIT 1
                        ) v ON true
                        ORDER BY v.updated_at DESC LIMIT 500
                        """
                    )
                )
                .mappings()
                .all()
            )
        return [AdminQuestionRecord.model_validate(dict(row)) for row in rows]

    def duplicates(self) -> list[DuplicateCandidateRecord]:
        with self.engine.connect() as connection:
            rows = (
                connection.execute(
                    text(
                        """
                        SELECT d.id AS duplicate_id, i.external_id AS imported_external_id,
                               i.slug AS imported_slug, d.existing_question_version_id,
                               v.title AS existing_title, d.similarity_score,
                               d.suggested_action, d.manual_reviewer_flag,
                               d.dimension_scores, d.created_at
                        FROM duplicate_candidates d
                        JOIN content_import_items i ON i.id=d.import_item_id
                        LEFT JOIN question_versions v ON v.id=d.existing_question_version_id
                        ORDER BY d.created_at DESC LIMIT 500
                        """
                    )
                )
                .mappings()
                .all()
            )
        return [
            DuplicateCandidateRecord.model_validate(
                {**dict(row), "similarity_score": float(row["similarity_score"])}
            )
            for row in rows
        ]

    def families(self) -> list[QuestionFamilyRecord]:
        with self.engine.connect() as connection:
            rows = (
                connection.execute(
                    text(
                        """
                        SELECT f.id AS family_id, f.slug, f.name,
                               c.slug AS canonical_competency,
                               f.core_problem_structure, f.variation_dimensions,
                               count(m.question_id) AS member_count, f.updated_at
                        FROM question_families f
                        LEFT JOIN competencies c ON c.id=f.canonical_competency_id
                        LEFT JOIN question_family_members m ON m.family_id=f.id
                        GROUP BY f.id, c.slug ORDER BY f.updated_at DESC
                        """
                    )
                )
                .mappings()
                .all()
            )
        return [QuestionFamilyRecord.model_validate(dict(row)) for row in rows]

    def gaps(self) -> list[CoverageGapRecord]:
        with self.engine.connect() as connection:
            rows = (
                connection.execute(
                    text(
                        """
                        SELECT g.id AS gap_id, c.slug AS competency_slug,
                               c.name AS competency_name, g.role_level, g.difficulty,
                               g.hosted_count, g.external_reference_count,
                               g.recommended_question_count, g.recommended_action,
                               g.status, g.created_at
                        FROM coverage_gap_briefs g
                        JOIN competencies c ON c.id=g.competency_id
                        ORDER BY CASE g.status WHEN 'open' THEN 0 ELSE 1 END,
                                 g.recommended_question_count DESC, c.slug
                        """
                    )
                )
                .mappings()
                .all()
            )
        return [CoverageGapRecord.model_validate(dict(row)) for row in rows]

    def recompute_gaps(self, principal: AuthenticatedPrincipal) -> GapRecomputeResult:
        with self.engine.begin() as connection:
            actor_id = ensure_user(connection, principal)
            result = connection.execute(
                text(
                    """
                    WITH coverage AS (
                        SELECT c.id, c.slug,
                               count(DISTINCT qc.question_id)::int AS hosted_count,
                               count(DISTINCT erc.external_reference_id)::int AS external_count
                        FROM competencies c
                        LEFT JOIN question_competencies qc ON qc.competency_id=c.id
                        LEFT JOIN external_reference_competencies erc
                          ON erc.competency_id=c.id
                        GROUP BY c.id
                    ), inserted AS (
                        INSERT INTO coverage_gap_briefs (
                            competency_id, role_level, difficulty, hosted_count,
                            external_reference_count, recommended_question_count,
                            recommended_action
                        )
                        SELECT coverage.id, 'senior', 'advanced', hosted_count,
                               external_count, greatest(1, 3-hosted_count),
                               'Author an independently original hosted question for ' ||
                               coverage.slug || ' and route it through technical ' ||
                               'and editorial review.'
                        FROM coverage
                        WHERE hosted_count < 3
                          AND NOT EXISTS (
                              SELECT 1 FROM coverage_gap_briefs existing
                              WHERE existing.competency_id=coverage.id
                                AND existing.role_level='senior'
                                AND existing.difficulty='advanced'
                                AND existing.status IN ('open', 'brief_generated', 'in_progress')
                          )
                        RETURNING id
                    )
                    SELECT count(*) FROM inserted
                    """
                )
            )
            created_count = int(result.scalar_one())
            open_count = int(
                connection.execute(
                    text(
                        "SELECT count(*) FROM coverage_gap_briefs "
                        "WHERE status IN ('open', 'brief_generated', 'in_progress')"
                    )
                ).scalar_one()
            )
            connection.execute(
                text(
                    """
                    UPDATE competencies c SET coverage_score=least(
                        1, ((SELECT count(*) FROM question_competencies qc
                             WHERE qc.competency_id=c.id) * 0.25) +
                           ((SELECT count(*) FROM external_reference_competencies erc
                             WHERE erc.competency_id=c.id) * 0.05)
                    ), last_updated_at=CURRENT_TIMESTAMP
                    """
                )
            )
            audit_event(
                connection,
                principal,
                actor_id,
                action="coverage.gaps_recomputed",
                resource_type="coverage_gap_brief",
                resource_id="global",
                details={"created_count": created_count, "open_gap_count": open_count},
            )
        return GapRecomputeResult(created_count=created_count, open_gap_count=open_count)

    def freshness(self) -> list[QuestionFreshnessRecord]:
        now = datetime.now(UTC)
        records: list[QuestionFreshnessRecord] = []
        for question in self.questions():
            age_days = max(0, (now - question.updated_at).days)
            status = "stale" if age_days > 365 else "review_due" if age_days > 180 else "current"
            records.append(
                QuestionFreshnessRecord(
                    question_id=question.question_id,
                    external_id=question.external_id,
                    title=question.title,
                    state=question.state,
                    updated_at=question.updated_at,
                    age_days=age_days,
                    freshness_status=status,
                )
            )
        return records

    def licenses(self) -> list[LicenseInventoryRecord]:
        with self.engine.connect() as connection:
            rows = (
                connection.execute(
                    text(
                        """
                        SELECT l.question_version_id, q.external_id, v.title,
                               l.rights_basis, l.license_identifier, l.provider,
                               l.expiration_date, l.created_at
                        FROM content_license_records l
                        JOIN question_versions v ON v.id=l.question_version_id
                        JOIN questions q ON q.id=v.question_id
                        ORDER BY l.created_at DESC
                        """
                    )
                )
                .mappings()
                .all()
            )
        return [LicenseInventoryRecord.model_validate(dict(row)) for row in rows]

    def provenance(self) -> list[ProvenanceInventoryRecord]:
        with self.engine.connect() as connection:
            rows = (
                connection.execute(
                    text(
                        """
                        SELECT p.question_version_id, q.external_id, v.title,
                               p.authoring_method, p.originality_statement,
                               p.source_notes, p.created_at
                        FROM provenance_records p
                        JOIN question_versions v ON v.id=p.question_version_id
                        JOIN questions q ON q.id=v.question_id
                        ORDER BY p.created_at DESC
                        """
                    )
                )
                .mappings()
                .all()
            )
        return [ProvenanceInventoryRecord.model_validate(dict(row)) for row in rows]
