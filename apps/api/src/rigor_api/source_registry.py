from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlparse
from uuid import UUID

from sqlalchemy import Engine, text

from .ingestion import IngestionError
from .persistence import audit_event, ensure_user
from .schemas import (
    AuthenticatedPrincipal,
    CatalogFilterOption,
    CatalogSourceStatus,
    CompetencyCoverage,
    ConnectorStatus,
    ContinuousCoverageStats,
    CoverageLevel,
    ExternalReference,
    ExternalReferenceFacets,
    PracticeCatalogSummary,
    PracticeSourceCount,
    SourceRegistryInput,
    SourceRegistryRecord,
    SourceReviewInput,
    SourceRightsStatus,
    SourceSyncInput,
    SourceSyncResult,
)

FULL_CONTENT_LEVELS = {
    CoverageLevel.open_license_full_content,
    CoverageLevel.partner_licensed_full_content,
    CoverageLevel.enterprise_owned_full_content,
}
FULL_CONTENT_RIGHTS = {
    SourceRightsStatus.open_license_verified,
    SourceRightsStatus.partner_license_verified,
    SourceRightsStatus.enterprise_owned_verified,
}
COLLECTABLE_LEVELS = {
    CoverageLevel.deeplink_only,
    CoverageLevel.metadata_only,
    CoverageLevel.user_private_import,
    CoverageLevel.open_license_full_content,
    CoverageLevel.partner_licensed_full_content,
    CoverageLevel.enterprise_owned_full_content,
    CoverageLevel.platform_original_full_content,
}


def normalize_domain(value: str) -> str:
    candidate = value.strip().casefold()
    parsed = urlparse(candidate if "://" in candidate else f"https://{candidate}")
    domain = (parsed.hostname or "").rstrip(".")
    if (
        not domain
        or parsed.username
        or parsed.password
        or any(character not in "abcdefghijklmnopqrstuvwxyz0123456789-." for character in domain)
    ):
        raise IngestionError(422, "canonical_domain must be a valid DNS hostname")
    return domain


def _source_record(row: Any) -> SourceRegistryRecord:
    values = dict(row)
    values["source_id"] = values.pop("id")
    return SourceRegistryRecord.model_validate(values)


class SourceRegistryRepository:
    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    def register(
        self, principal: AuthenticatedPrincipal, source: SourceRegistryInput
    ) -> SourceRegistryRecord:
        domain = normalize_domain(source.canonical_domain)
        with self.engine.begin() as connection:
            actor_id = ensure_user(connection, principal)
            try:
                row = (
                    connection.execute(
                        text(
                            """
                        INSERT INTO source_registry (
                            source_name, canonical_domain, source_category,
                            discovery_method, access_method, estimated_content_volume, priority
                        ) VALUES (
                            :source_name, :domain, :category, :discovery_method,
                            :access_method, :estimated_volume, :priority
                        ) RETURNING *
                        """
                        ),
                        {
                            "source_name": source.source_name,
                            "domain": domain,
                            "category": source.source_category,
                            "discovery_method": source.discovery_method,
                            "access_method": source.access_method,
                            "estimated_volume": source.estimated_content_volume,
                            "priority": source.priority,
                        },
                    )
                    .mappings()
                    .one()
                )
            except Exception as exc:
                if "source_registry_canonical_domain_key" in str(exc):
                    raise IngestionError(409, "Source domain is already registered") from exc
                raise
            audit_event(
                connection,
                principal,
                actor_id,
                action="source.registered",
                resource_type="source",
                resource_id=str(row["id"]),
                details={"canonical_domain": domain, "coverage_level": "DISCOVERY_ONLY"},
            )
            return _source_record(row)

    def list(
        self,
        principal: AuthenticatedPrincipal,
        *,
        connector_status: ConnectorStatus | None = None,
        coverage_level: CoverageLevel | None = None,
    ) -> list[SourceRegistryRecord]:
        conditions: list[str] = []
        parameters: dict[str, Any] = {}
        if connector_status:
            conditions.append("connector_status=:connector_status")
            parameters["connector_status"] = connector_status.value
        if coverage_level:
            conditions.append("coverage_level=:coverage_level")
            parameters["coverage_level"] = coverage_level.value
        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        with self.engine.begin() as connection:
            ensure_user(connection, principal)
            rows = (
                connection.execute(
                    text(
                        f"""
                    SELECT * FROM source_registry {where}
                    ORDER BY priority DESC, source_name ASC
                    """
                    ),
                    parameters,
                )
                .mappings()
                .all()
            )
        return [_source_record(row) for row in rows]

    def get(self, principal: AuthenticatedPrincipal, source_id: UUID) -> SourceRegistryRecord:
        with self.engine.begin() as connection:
            ensure_user(connection, principal)
            row = (
                connection.execute(
                    text("SELECT * FROM source_registry WHERE id=:source_id"),
                    {"source_id": source_id},
                )
                .mappings()
                .one_or_none()
            )
            if row is None:
                raise IngestionError(404, "Source not found")
            return _source_record(row)

    def review(
        self,
        principal: AuthenticatedPrincipal,
        source_id: UUID,
        review: SourceReviewInput,
    ) -> SourceRegistryRecord:
        if (
            review.coverage_level in FULL_CONTENT_LEVELS
            and review.rights_status not in FULL_CONTENT_RIGHTS
        ):
            raise IngestionError(422, "Full-content coverage requires verified compatible rights")
        if (
            review.coverage_level == CoverageLevel.blocked
            and review.rights_status != SourceRightsStatus.blocked
        ):
            raise IngestionError(422, "BLOCKED coverage requires blocked rights status")
        if review.connector_status == ConnectorStatus.approved and review.coverage_level in {
            CoverageLevel.blocked,
            CoverageLevel.discovery_only,
            CoverageLevel.abstract_signal_only,
        }:
            raise IngestionError(422, "This coverage level cannot approve an automated connector")
        with self.engine.begin() as connection:
            actor_id = ensure_user(connection, principal)
            row = (
                connection.execute(
                    text(
                        """
                    UPDATE source_registry SET
                        rights_status=:rights_status, coverage_level=:coverage_level,
                        collection_mode=:collection_mode, connector_status=:connector_status,
                        connector_type=:connector_type,
                        connector_configuration=CAST(:configuration AS jsonb),
                        next_scheduled_sync=:next_sync, last_reviewed_at=CURRENT_TIMESTAMP,
                        reviewed_by=:actor_id, pause_reason=:review_notes,
                        updated_at=CURRENT_TIMESTAMP
                    WHERE id=:source_id RETURNING *
                    """
                    ),
                    {
                        "rights_status": review.rights_status.value,
                        "coverage_level": review.coverage_level.value,
                        "collection_mode": review.collection_mode,
                        "connector_status": review.connector_status.value,
                        "connector_type": review.connector_type,
                        "configuration": json.dumps(review.connector_configuration),
                        "next_sync": review.next_scheduled_sync,
                        "actor_id": actor_id,
                        "review_notes": review.review_notes,
                        "source_id": source_id,
                    },
                )
                .mappings()
                .one_or_none()
            )
            if row is None:
                raise IngestionError(404, "Source not found")
            audit_event(
                connection,
                principal,
                actor_id,
                action="source.reviewed",
                resource_type="source",
                resource_id=str(source_id),
                details={
                    "rights_status": review.rights_status.value,
                    "coverage_level": review.coverage_level.value,
                    "connector_status": review.connector_status.value,
                    "review_notes": review.review_notes,
                },
            )
            return _source_record(row)

    def sync(
        self,
        principal: AuthenticatedPrincipal,
        source_id: UUID,
        payload: SourceSyncInput,
    ) -> SourceSyncResult:
        completed = datetime.now(UTC)
        with self.engine.begin() as connection:
            actor_id = ensure_user(connection, principal)
            source = (
                connection.execute(
                    text("SELECT * FROM source_registry WHERE id=:source_id FOR UPDATE"),
                    {"source_id": source_id},
                )
                .mappings()
                .one_or_none()
            )
            if source is None:
                raise IngestionError(404, "Source not found")
            coverage = CoverageLevel(str(source["coverage_level"]))
            if source["connector_status"] != ConnectorStatus.approved.value:
                raise IngestionError(409, "Only a reviewed and approved connector can synchronize")
            if coverage not in COLLECTABLE_LEVELS:
                raise IngestionError(409, "Source coverage does not permit reference collection")
            sync_id = connection.execute(
                text(
                    """
                    INSERT INTO source_sync_runs (
                        source_id, sync_mode, status, cursor_before, started_by
                    ) VALUES (
                        :source_id, :mode, 'running', CAST(:cursor AS jsonb), :actor_id
                    ) RETURNING id
                    """
                ),
                {
                    "source_id": source_id,
                    "mode": payload.sync_mode,
                    "cursor": json.dumps(payload.cursor_before),
                    "actor_id": actor_id,
                },
            ).scalar_one()
            created = 0
            updated = 0
            seen_urls: list[str] = []
            source_domain = str(source["canonical_domain"])
            competency_ids = {
                str(row["slug"]): row["id"]
                for row in connection.execute(text("SELECT id, slug FROM competencies")).mappings()
            }
            for reference in payload.references:
                self._validate_reference(
                    reference.canonical_url, source_domain, coverage, reference.abstract
                )
                unknown_competencies = sorted(
                    set(reference.competency_slugs) - competency_ids.keys()
                )
                if unknown_competencies:
                    raise IngestionError(
                        422,
                        "Unknown competency mappings: " + ", ".join(unknown_competencies),
                    )
                seen_urls.append(reference.canonical_url)
                metadata = {
                    **reference.source_metadata,
                    "patterns": reference.patterns,
                    "competency_slugs": reference.competency_slugs,
                }
                upserted = (
                    connection.execute(
                        text(
                            """
                        INSERT INTO external_question_references (
                            source_id, source_external_id, canonical_url, title, abstract,
                            difficulty, topic_metadata, source_metadata,
                            source_availability, access_tier, technology_freshness,
                            last_seen_at, last_verified_at, last_content_change_at
                        ) VALUES (
                            :source_id, :external_id, :url, :title, :abstract, :difficulty,
                            CAST(:topics AS jsonb), CAST(:metadata AS jsonb),
                            :availability, :access_tier, :freshness,
                            CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                        )
                        ON CONFLICT (source_id, canonical_url) DO UPDATE SET
                            source_external_id=EXCLUDED.source_external_id,
                            title=EXCLUDED.title, abstract=EXCLUDED.abstract,
                            difficulty=EXCLUDED.difficulty,
                            topic_metadata=EXCLUDED.topic_metadata,
                            source_metadata=EXCLUDED.source_metadata,
                            source_availability=EXCLUDED.source_availability,
                            access_tier=EXCLUDED.access_tier,
                            technology_freshness=EXCLUDED.technology_freshness,
                            last_seen_at=CURRENT_TIMESTAMP,
                            last_verified_at=CURRENT_TIMESTAMP,
                            last_content_change_at=CASE WHEN
                                external_question_references.title IS DISTINCT FROM EXCLUDED.title
                                OR external_question_references.source_metadata
                                   IS DISTINCT FROM EXCLUDED.source_metadata
                                THEN CURRENT_TIMESTAMP
                                ELSE external_question_references.last_content_change_at END
                        RETURNING id, (xmax = 0) AS inserted
                        """
                        ),
                        {
                            "source_id": source_id,
                            "external_id": reference.source_external_id,
                            "url": reference.canonical_url,
                            "title": reference.title,
                            "abstract": reference.abstract,
                            "difficulty": reference.difficulty,
                            "topics": json.dumps(reference.topic_metadata),
                            "metadata": json.dumps(metadata),
                            "availability": reference.source_availability,
                            "access_tier": reference.access_tier,
                            "freshness": reference.technology_freshness,
                        },
                    )
                    .mappings()
                    .one()
                )
                reference_id = upserted["id"]
                was_inserted = bool(upserted["inserted"])
                created += int(was_inserted)
                updated += int(not was_inserted)
                connection.execute(
                    text(
                        "DELETE FROM external_reference_competencies "
                        "WHERE external_reference_id=:reference_id"
                    ),
                    {"reference_id": reference_id},
                )
                for competency_slug in dict.fromkeys(reference.competency_slugs):
                    connection.execute(
                        text(
                            """
                            INSERT INTO external_reference_competencies (
                                external_reference_id, competency_id, confidence
                            ) VALUES (:reference_id, :competency_id, 0.85)
                            """
                        ),
                        {
                            "reference_id": reference_id,
                            "competency_id": competency_ids[competency_slug],
                        },
                    )
            unavailable = 0
            if payload.complete_snapshot:
                unavailable = connection.execute(
                    text(
                        """
                        UPDATE external_question_references SET
                            source_availability='unavailable', last_verified_at=CURRENT_TIMESTAMP
                        WHERE source_id=:source_id
                          AND NOT (canonical_url = ANY(:seen_urls))
                          AND source_availability='available'
                        """
                    ),
                    {"source_id": source_id, "seen_urls": seen_urls or [""]},
                ).rowcount
            indexed = connection.execute(
                text(
                    "SELECT count(*) FROM external_question_references WHERE source_id=:source_id"
                ),
                {"source_id": source_id},
            ).scalar_one()
            connection.execute(
                text(
                    """
                    UPDATE source_sync_runs SET
                        status='completed', cursor_after=CAST(:cursor_after AS jsonb),
                        discovered_count=:discovered, created_count=:created,
                        updated_count=:updated, deleted_count=:unavailable,
                        completed_at=:completed
                    WHERE id=:sync_id
                    """
                ),
                {
                    "cursor_after": json.dumps(payload.cursor_after),
                    "discovered": len(payload.references),
                    "created": created,
                    "updated": updated,
                    "unavailable": unavailable,
                    "completed": completed,
                    "sync_id": sync_id,
                },
            )
            connection.execute(
                text(
                    """
                    UPDATE source_registry SET
                        actual_indexed_volume=:indexed,
                        last_successful_sync=:completed,
                        failure_count=0, updated_at=CURRENT_TIMESTAMP
                    WHERE id=:source_id
                    """
                ),
                {"indexed": indexed, "completed": completed, "source_id": source_id},
            )
            audit_event(
                connection,
                principal,
                actor_id,
                action="source.synchronized",
                resource_type="source",
                resource_id=str(source_id),
                details={
                    "sync_id": str(sync_id),
                    "created": created,
                    "updated": updated,
                    "unavailable": unavailable,
                },
            )
            return SourceSyncResult(
                sync_id=UUID(str(sync_id)),
                source_id=source_id,
                discovered_count=len(payload.references),
                created_count=created,
                updated_count=updated,
                unavailable_count=unavailable,
                completed_at=completed,
            )

    def external_references(
        self,
        *,
        query: str | None,
        source_id: UUID | None,
        difficulty: str | None,
        competency: str | None,
        page: int,
        page_size: int,
    ) -> tuple[list[ExternalReference], int]:
        conditions = ["s.coverage_level <> 'BLOCKED'"]
        parameters: dict[str, Any] = {
            "limit": page_size,
            "offset": (page - 1) * page_size,
        }
        if query:
            conditions.append("r.search_document @@ websearch_to_tsquery('english', :query)")
            parameters["query"] = query
        if source_id:
            conditions.append("r.source_id=:source_id")
            parameters["source_id"] = source_id
        if difficulty:
            conditions.append("r.difficulty=:difficulty")
            parameters["difficulty"] = difficulty
        if competency:
            conditions.append(
                "EXISTS (SELECT 1 FROM external_reference_competencies erc "
                "JOIN competencies c ON c.id=erc.competency_id "
                "WHERE erc.external_reference_id=r.id AND c.slug=:competency)"
            )
            parameters["competency"] = competency
        where = " AND ".join(conditions)
        with self.engine.connect() as connection:
            total = connection.execute(
                text(
                    f"""
                    SELECT count(*) FROM external_question_references r
                    JOIN source_registry s ON s.id=r.source_id WHERE {where}
                    """
                ),
                parameters,
            ).scalar_one()
            rows = (
                connection.execute(
                    text(
                        f"""
                    SELECT r.id AS reference_id, r.source_id, s.source_name,
                           s.canonical_domain, s.coverage_level, r.canonical_url,
                           r.title, r.abstract, r.difficulty, r.topic_metadata,
                           COALESCE(r.source_metadata->'patterns', '[]'::jsonb) AS patterns,
                           COALESCE((
                               SELECT jsonb_agg(c.slug ORDER BY c.slug)
                               FROM external_reference_competencies erc
                               JOIN competencies c ON c.id=erc.competency_id
                               WHERE erc.external_reference_id=r.id
                           ), '[]'::jsonb) AS competency_slugs,
                           r.source_availability, r.access_tier, r.technology_freshness,
                           r.first_seen_at, r.last_seen_at, r.last_verified_at,
                           r.review_due_at
                    FROM external_question_references r
                    JOIN source_registry s ON s.id=r.source_id
                    WHERE {where}
                    ORDER BY r.last_seen_at DESC, r.id
                    LIMIT :limit OFFSET :offset
                    """
                    ),
                    parameters,
                )
                .mappings()
                .all()
            )
        return [ExternalReference.model_validate(dict(row)) for row in rows], int(total)

    def external_reference_facets(self) -> ExternalReferenceFacets:
        with self.engine.connect() as connection:
            source_rows = (
                connection.execute(
                    text(
                        """
                        SELECT s.id::text AS value, s.source_name AS label, count(r.id) AS count
                        FROM source_registry s
                        JOIN external_question_references r ON r.source_id=s.id
                        WHERE s.coverage_level <> 'BLOCKED'
                        GROUP BY s.id, s.source_name ORDER BY count(r.id) DESC, s.source_name
                        """
                    )
                )
                .mappings()
                .all()
            )
            difficulty_rows = (
                connection.execute(
                    text(
                        """
                        SELECT difficulty AS value, initcap(difficulty) AS label, count(*) AS count
                        FROM external_question_references r
                        JOIN source_registry s ON s.id=r.source_id
                        WHERE s.coverage_level <> 'BLOCKED' AND difficulty IS NOT NULL
                        GROUP BY difficulty ORDER BY count(*) DESC, difficulty
                        """
                    )
                )
                .mappings()
                .all()
            )
            competency_rows = (
                connection.execute(
                    text(
                        """
                        SELECT c.slug AS value, c.name AS label,
                               count(DISTINCT erc.external_reference_id) AS count
                        FROM competencies c
                        JOIN external_reference_competencies erc ON erc.competency_id=c.id
                        JOIN external_question_references r ON r.id=erc.external_reference_id
                        JOIN source_registry s ON s.id=r.source_id
                        WHERE s.coverage_level <> 'BLOCKED'
                        GROUP BY c.id
                        ORDER BY count(DISTINCT erc.external_reference_id) DESC, c.name
                        """
                    )
                )
                .mappings()
                .all()
            )
        return ExternalReferenceFacets(
            sources=[CatalogFilterOption.model_validate(dict(row)) for row in source_rows],
            difficulties=[
                CatalogFilterOption.model_validate(dict(row)) for row in difficulty_rows
            ],
            competencies=[
                CatalogFilterOption.model_validate(dict(row)) for row in competency_rows
            ],
        )

    def practice_summary(self) -> PracticeCatalogSummary:
        with self.engine.connect() as connection:
            values = (
                connection.execute(
                    text(
                        """
                        SELECT
                          (SELECT count(*) FROM external_question_references r
                           JOIN source_registry s ON s.id=r.source_id
                           WHERE s.coverage_level <> 'BLOCKED') AS external_references,
                          (SELECT count(*) FROM questions WHERE record_type IN (
                             'platform_original_hosted_question', 'licensed_hosted_question',
                             'open_license_hosted_question')) AS hosted_records,
                          (SELECT count(*) FROM question_versions WHERE state IN (
                             'awaiting_technical_review'::content_state,
                             'awaiting_editorial_review'::content_state)) AS awaiting_review,
                          (SELECT count(*) FROM questions q JOIN question_versions v
                             ON v.id=q.current_published_version_id
                           WHERE v.state='published'::content_state) AS published_hosted_questions,
                          (SELECT count(*) FROM source_registry
                           WHERE connector_status='approved') AS approved_sources,
                          (SELECT max(last_successful_sync) FROM source_registry)
                            AS last_successful_collection
                        """
                    )
                )
                .mappings()
                .one()
            )
            source_rows = (
                connection.execute(
                    text(
                        """
                        SELECT s.id AS source_id, s.source_name, count(r.id) AS reference_count
                        FROM source_registry s
                        JOIN external_question_references r ON r.source_id=s.id
                        WHERE s.coverage_level <> 'BLOCKED'
                        GROUP BY s.id ORDER BY count(r.id) DESC, s.source_name
                        """
                    )
                )
                .mappings()
                .all()
            )
        return PracticeCatalogSummary(
            **dict(values),
            source_counts=[PracticeSourceCount.model_validate(dict(row)) for row in source_rows],
        )

    def catalog_status(self) -> list[CatalogSourceStatus]:
        with self.engine.connect() as connection:
            rows = (
                connection.execute(
                    text(
                        """
                        SELECT s.id AS source_id, s.source_name, s.canonical_domain,
                               s.connector_status, s.last_successful_sync AS last_run,
                               s.actual_indexed_volume AS references_collected,
                               COALESCE(latest.updated_count, 0) AS references_updated,
                               s.failure_count AS failures, s.rights_status, s.coverage_level,
                               latest.failure_message AS last_error,
                               CASE
                                 WHEN s.connector_status='approved'
                                   THEN 'Run approved collector'
                                 WHEN s.connector_status='unreviewed'
                                   THEN 'Complete rights review'
                                 WHEN s.connector_status='failing'
                                   THEN 'Inspect failure and retry'
                                 WHEN s.connector_status='paused'
                                   THEN 'Review pause reason'
                                 ELSE 'No collection action available'
                               END AS next_available_action
                        FROM source_registry s
                        LEFT JOIN LATERAL (
                            SELECT updated_count, failure_message
                            FROM source_sync_runs run WHERE run.source_id=s.id
                            ORDER BY started_at DESC LIMIT 1
                        ) latest ON true
                        ORDER BY s.actual_indexed_volume DESC, s.source_name
                        """
                    )
                )
                .mappings()
                .all()
            )
        return [CatalogSourceStatus.model_validate(dict(row)) for row in rows]

    def coverage(self, foundation_manifest_entries: int) -> ContinuousCoverageStats:
        with self.engine.connect() as connection:
            values = (
                connection.execute(
                    text(
                        """
                    SELECT
                      (SELECT count(*) FROM source_registry) AS discovered_sources,
                      (SELECT count(*) FROM source_registry
                       WHERE connector_status='approved') AS approved_sources,
                      (SELECT count(*) FROM source_registry
                       WHERE coverage_level='BLOCKED') AS blocked_sources,
                      (SELECT count(*) FROM external_question_references) AS external_references,
                      (SELECT count(*) FROM questions
                       WHERE record_type='platform_original_hosted_question')
                        AS hosted_original_questions,
                      (SELECT count(*) FROM questions
                       WHERE record_type='licensed_hosted_question') AS hosted_licensed_questions,
                      (SELECT count(*) FROM questions
                       WHERE record_type='open_license_hosted_question') AS open_license_questions,
                      (SELECT count(DISTINCT v.id) FROM question_versions v
                       JOIN content_license_records l ON l.question_version_id=v.id)
                        AS schema_complete_questions,
                      (SELECT count(DISTINCT question_version_id) FROM validation_runs
                       WHERE status='passed') AS executable_validated_questions,
                      (SELECT count(DISTINCT a.question_version_id)
                       FROM review_assignments a JOIN review_decisions d
                         ON d.review_assignment_id=a.id
                       WHERE a.kind='technical'::review_kind
                         AND d.outcome='approved'::review_outcome)
                        AS technically_reviewed_questions,
                      (SELECT count(DISTINCT a.question_version_id)
                       FROM review_assignments a JOIN review_decisions d
                         ON d.review_assignment_id=a.id
                       WHERE a.kind='editorial'::review_kind
                         AND d.outcome='approved'::review_outcome)
                        AS editorially_reviewed_questions,
                      (SELECT count(*) FROM question_versions
                       WHERE state='published'::content_state) AS published_questions,
                      (SELECT count(*) FROM question_families) AS question_families,
                      (SELECT count(*) FROM questions
                       WHERE record_type='question_variation') AS meaningful_variants,
                      (SELECT count(*) FROM questions
                       WHERE record_type='user_private_question') AS user_private_questions,
                      (SELECT count(*) FROM questions
                       WHERE record_type='enterprise_private_question')
                        AS enterprise_private_questions,
                      (SELECT count(*) FROM question_versions
                       WHERE state='deprecated'::content_state) AS deprecated_questions,
                      (SELECT count(*) FROM external_question_references
                       WHERE source_availability <> 'available')
                        AS unavailable_external_references,
                      (SELECT count(*) FROM coverage_gap_briefs
                       WHERE status IN ('open', 'brief_generated', 'in_progress'))
                        AS open_coverage_gaps,
                      (SELECT max(last_successful_sync) FROM source_registry)
                        AS last_synchronization_time
                    """
                    )
                )
                .mappings()
                .one()
            )
        return ContinuousCoverageStats(
            foundation_manifest_entries=foundation_manifest_entries,
            planned_questions=foundation_manifest_entries,
            **dict(values),
        )

    def competency_coverage(self) -> list[CompetencyCoverage]:
        with self.engine.connect() as connection:
            rows = (
                connection.execute(
                    text(
                        """
                    SELECT c.id AS competency_id, c.slug, c.name, parent.slug AS parent_slug,
                           count(DISTINCT qc.question_id) AS hosted_question_count,
                           count(DISTINCT erc.external_reference_id) AS external_reference_count,
                           count(DISTINCT q.current_published_version_id)
                             FILTER (WHERE q.current_published_version_id IS NOT NULL)
                             AS published_question_count,
                           c.coverage_score, c.last_updated_at
                    FROM competencies c
                    LEFT JOIN competencies parent ON parent.id=c.parent_competency_id
                    LEFT JOIN question_competencies qc ON qc.competency_id=c.id
                    LEFT JOIN questions q ON q.id=qc.question_id
                    LEFT JOIN external_reference_competencies erc ON erc.competency_id=c.id
                    GROUP BY c.id, parent.slug ORDER BY c.slug
                    """
                    )
                )
                .mappings()
                .all()
            )
        return [
            CompetencyCoverage.model_validate(
                {**dict(row), "coverage_score": float(row["coverage_score"])}
            )
            for row in rows
        ]

    @staticmethod
    def _validate_reference(
        url: str, source_domain: str, coverage: CoverageLevel, abstract: str | None
    ) -> None:
        parsed = urlparse(url)
        hostname = (parsed.hostname or "").casefold()
        if (
            parsed.scheme != "https"
            or not hostname
            or not (hostname == source_domain or hostname.endswith(f".{source_domain}"))
        ):
            raise IngestionError(422, "Reference URL must be HTTPS on the reviewed source domain")
        if parsed.username or parsed.password or parsed.fragment:
            raise IngestionError(422, "Reference URL contains unsupported credentials or fragment")
        if coverage == CoverageLevel.deeplink_only and abstract:
            raise IngestionError(422, "DEEPLINK_ONLY sources cannot store content abstracts")
