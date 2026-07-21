from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import Engine, text

from .ingestion import IngestionError
from .persistence import audit_event, ensure_user
from .schemas import (
    AuthenticatedPrincipal,
    ContentImportItem,
    ContentImportReport,
    ContentImportSummary,
    ImportErrorItem,
    ImportRollbackResult,
    ImportStageResult,
)


class ContentImportRepository:
    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    def list(self, principal: AuthenticatedPrincipal) -> list[ContentImportSummary]:
        with self.engine.begin() as connection:
            ensure_user(connection, principal)
            rows = (
                connection.execute(
                    text(
                        """
                    SELECT id AS import_id, source_filename, source_method, status, dry_run,
                           question_count, accepted_count, rejected_count, warning_count,
                           rollback_available, started_at, completed_at
                    FROM content_imports ORDER BY started_at DESC LIMIT 200
                    """
                    )
                )
                .mappings()
                .all()
            )
        return [ContentImportSummary.model_validate(dict(row)) for row in rows]

    def get(self, principal: AuthenticatedPrincipal, import_id: UUID) -> ContentImportReport:
        with self.engine.begin() as connection:
            ensure_user(connection, principal)
            import_row = (
                connection.execute(
                    text(
                        """
                    SELECT id AS import_id, source_filename, source_method, status, dry_run,
                           question_count, accepted_count, rejected_count, warning_count,
                           rollback_available, started_at, completed_at
                    FROM content_imports WHERE id=:import_id
                    """
                    ),
                    {"import_id": import_id},
                )
                .mappings()
                .one_or_none()
            )
            if import_row is None:
                raise IngestionError(404, "Content import not found")
            item_rows = (
                connection.execute(
                    text(
                        """
                    SELECT id, ordinal, source_path, external_id, slug, status, errors,
                           warnings, normalized_hash, similarity_score, question_version_id
                    FROM content_import_items WHERE import_id=:import_id ORDER BY ordinal
                    """
                    ),
                    {"import_id": import_id},
                )
                .mappings()
                .all()
            )
            items: list[ContentImportItem] = []
            for item in item_rows:
                stages = (
                    connection.execute(
                        text(
                            """
                        SELECT stage, status, findings, metrics
                        FROM content_import_stage_results
                        WHERE import_item_id=:item_id ORDER BY started_at, stage
                        """
                        ),
                        {"item_id": item["id"]},
                    )
                    .mappings()
                    .all()
                )
                values = dict(item)
                values.pop("id")
                if values["similarity_score"] is not None:
                    values["similarity_score"] = float(values["similarity_score"])
                values["stages"] = [
                    ImportStageResult.model_validate(dict(stage)) for stage in stages
                ]
                items.append(ContentImportItem.model_validate(values))
        return ContentImportReport.model_validate({**dict(import_row), "items": items})

    def errors(self, principal: AuthenticatedPrincipal, import_id: UUID) -> list[ImportErrorItem]:
        report = self.get(principal, import_id)
        return [
            ImportErrorItem(
                ordinal=item.ordinal,
                source_path=item.source_path,
                external_id=item.external_id,
                errors=item.errors,
            )
            for item in report.items
            if item.errors
        ]

    def rollback(self, principal: AuthenticatedPrincipal, import_id: UUID) -> ImportRollbackResult:
        with self.engine.begin() as connection:
            actor_id = ensure_user(connection, principal)
            import_row = (
                connection.execute(
                    text(
                        """
                    SELECT status, rollback_available FROM content_imports
                    WHERE id=:import_id FOR UPDATE
                    """
                    ),
                    {"import_id": import_id},
                )
                .mappings()
                .one_or_none()
            )
            if import_row is None:
                raise IngestionError(404, "Content import not found")
            if import_row["status"] == "rolled_back":
                return ImportRollbackResult(import_id=import_id, rolled_back_versions=0)
            if not import_row["rollback_available"]:
                raise IngestionError(409, "This import has no rollback-eligible database changes")
            version_rows = (
                connection.execute(
                    text(
                        """
                    SELECT v.id, v.question_id, v.state::text AS state
                    FROM content_import_items i JOIN question_versions v
                      ON v.id=i.question_version_id
                    WHERE i.import_id=:import_id
                      AND v.source_revision=:source_revision
                    FOR UPDATE OF v
                    """
                    ),
                    {
                        "import_id": import_id,
                        "source_revision": f"import:{import_id}",
                    },
                )
                .mappings()
                .all()
            )
            protected = [
                str(row["id"])
                for row in version_rows
                if row["state"] in {"approved", "published", "deprecated"}
            ]
            if protected:
                raise IngestionError(
                    409,
                    "Import contains reviewed or published versions and cannot be rolled back: "
                    + ", ".join(protected),
                )
            version_ids = [row["id"] for row in version_rows]
            question_ids = [row["question_id"] for row in version_rows]
            if version_ids:
                connection.execute(
                    text(
                        "DELETE FROM review_decisions WHERE review_assignment_id IN "
                        "(SELECT id FROM review_assignments WHERE question_version_id=ANY(:ids))"
                    ),
                    {"ids": version_ids},
                )
                connection.execute(
                    text(
                        "UPDATE duplicate_candidates SET existing_question_version_id=NULL "
                        "WHERE existing_question_version_id=ANY(:ids)"
                    ),
                    {"ids": version_ids},
                )
                connection.execute(
                    text(
                        "UPDATE content_import_items SET question_version_id=NULL "
                        "WHERE question_version_id=ANY(:ids)"
                    ),
                    {"ids": version_ids},
                )
                connection.execute(
                    text(
                        "UPDATE content_import_items SET status='rolled_back' "
                        "WHERE import_id=:import_id"
                    ),
                    {"import_id": import_id},
                )
                connection.execute(
                    text("DELETE FROM question_versions WHERE id=ANY(:ids)"),
                    {"ids": version_ids},
                )
                connection.execute(
                    text(
                        "DELETE FROM questions q WHERE q.id=ANY(:question_ids) "
                        "AND NOT EXISTS (SELECT 1 FROM question_versions v "
                        "WHERE v.question_id=q.id)"
                    ),
                    {"question_ids": question_ids},
                )
            connection.execute(
                text(
                    """
                    UPDATE content_imports SET status='rolled_back', rollback_available=false,
                        rolled_back_at=CURRENT_TIMESTAMP
                    WHERE id=:import_id
                    """
                ),
                {"import_id": import_id},
            )
            audit_event(
                connection,
                principal,
                actor_id,
                action="content.import.rolled_back",
                resource_type="content_import",
                resource_id=str(import_id),
                details={"rolled_back_versions": len(version_ids)},
            )
            return ImportRollbackResult(import_id=import_id, rolled_back_versions=len(version_ids))

    def payload(self, principal: AuthenticatedPrincipal, import_id: UUID) -> bytes:
        report = self.get(principal, import_id)
        return report.model_dump_json(indent=2).encode("utf-8")


def report_dict(report: ContentImportReport) -> dict[str, Any]:
    return report.model_dump(mode="json")
