from __future__ import annotations

import hashlib
import json
from uuid import UUID

from sqlalchemy import Engine, text

from .import_reports import ContentImportRepository
from .ingestion import ContentIngestionEngine, IngestionError
from .persistence import audit_event, ensure_user
from .schemas import AuthenticatedPrincipal, ContentFactoryBatchInput, ContentImportReport


class ContentFactory:
    """Controlled boundary for AI-assisted batches; it never publishes content."""

    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    def run(
        self, principal: AuthenticatedPrincipal, batch: ContentFactoryBatchInput
    ) -> ContentImportReport:
        tracks = {question.primary_track for question in batch.questions}
        if len(tracks) > 1 and not batch.allow_mixed_tracks:
            raise IngestionError(
                422,
                "Content factory batches must use one primary track unless mixed mode is explicit",
            )
        payload = [question.model_dump(mode="json") for question in batch.questions]
        result = ContentIngestionEngine(self.engine).import_upload(
            principal,
            filename="content-factory-batch.json",
            content=json.dumps(payload).encode("utf-8"),
            dry_run=batch.dry_run,
            source_method_override="generation",
        )
        import_id = UUID(result.import_id)
        report = ContentImportRepository(self.engine).get(principal, import_id)
        self._record_traces(principal, report, batch)
        return ContentImportRepository(self.engine).get(principal, import_id)

    def _record_traces(
        self,
        principal: AuthenticatedPrincipal,
        report: ContentImportReport,
        batch: ContentFactoryBatchInput,
    ) -> None:
        by_ordinal = {item.ordinal: item for item in report.items}
        with self.engine.begin() as connection:
            actor_id = ensure_user(connection, principal)
            rows = (
                connection.execute(
                    text(
                        "SELECT id, ordinal FROM content_import_items "
                        "WHERE import_id=:import_id ORDER BY ordinal"
                    ),
                    {"import_id": report.import_id},
                )
                .mappings()
                .all()
            )
            for row in rows:
                item = by_ordinal[int(row["ordinal"])]
                input_value = f"{batch.prompt_version}:{item.external_id}:{batch.model_identifier}"
                input_hash = hashlib.sha256(input_value.encode("utf-8")).hexdigest()
                output_hash = (
                    item.normalized_hash
                    or hashlib.sha256(
                        json.dumps(item.errors, sort_keys=True).encode("utf-8")
                    ).hexdigest()
                )
                validation = {
                    stage.stage: {
                        "status": stage.status,
                        "findings": stage.findings,
                        "metrics": stage.metrics,
                    }
                    for stage in item.stages
                }
                connection.execute(
                    text(
                        """
                        INSERT INTO generation_traces (
                            import_item_id, manifest_id, stage, prompt_version,
                            model_provider, model_identifier, input_hash, output_hash,
                            validation_results
                        ) VALUES (
                            :item_id, :manifest_id, 'validated_draft_generation',
                            :prompt_version, :provider, :model_identifier,
                            :input_hash, :output_hash, CAST(:validation AS jsonb)
                        )
                        """
                    ),
                    {
                        "item_id": row["id"],
                        "manifest_id": item.external_id or f"ordinal-{item.ordinal}",
                        "prompt_version": batch.prompt_version,
                        "provider": batch.model_provider,
                        "model_identifier": batch.model_identifier,
                        "input_hash": input_hash,
                        "output_hash": output_hash,
                        "validation": json.dumps(validation),
                    },
                )
            audit_event(
                connection,
                principal,
                actor_id,
                action="content.factory.batch_completed",
                resource_type="content_import",
                resource_id=str(report.import_id),
                details={
                    "question_count": report.question_count,
                    "accepted": report.accepted_count,
                    "rejected": report.rejected_count,
                    "dry_run": report.dry_run,
                    "tracks": sorted({question.primary_track for question in batch.questions}),
                    "prompt_version": batch.prompt_version,
                    "model_provider": batch.model_provider,
                    "model_identifier": batch.model_identifier,
                },
            )
