#!/usr/bin/env python3
"""Administrative CLI for the universal content-ingestion pipeline."""

from __future__ import annotations

import argparse
import io
import json
import sys
import zipfile
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID

from rigor_api.auth import ROLE_PERMISSIONS
from rigor_api.config import Settings
from rigor_api.database import create_database_engine
from rigor_api.import_reports import ContentImportRepository
from rigor_api.ingestion import ContentIngestionEngine, IngestionError
from rigor_api.schemas import AuthenticatedPrincipal, Role


def _principal() -> AuthenticatedPrincipal:
    role = Role.platform_administrator
    return AuthenticatedPrincipal(
        subject_id="local-content-cli",
        email="content-cli@rigor.test",
        display_name="Content CLI",
        roles=[role],
        permissions=sorted(ROLE_PERMISSIONS[role]),
        authentication_provider="local-cli",
        token_issued_at=datetime.now(UTC),
        correlation_id="content-cli",
    )


def _read_path(path_value: str) -> tuple[str, bytes]:
    path = Path(path_value).expanduser().resolve()
    if not path.exists():
        raise IngestionError(404, f"Content path does not exist: {path}")
    if path.is_file():
        return path.name, path.read_bytes()
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for file_path in sorted(item for item in path.rglob("*") if item.is_file()):
            archive.write(file_path, file_path.relative_to(path).as_posix())
    return f"{path.name}.zip", buffer.getvalue()


def _dump(value: Any) -> None:
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json")
    elif hasattr(value, "to_json"):
        print(value.to_json(), end="")
        return
    elif hasattr(value, "__dataclass_fields__"):
        value = asdict(value)
    print(json.dumps(value, indent=2, default=str))


def _import_path(path: str, *, dry_run: bool) -> tuple[Any, ContentImportRepository]:
    filename, content = _read_path(path)
    engine = create_database_engine(Settings())
    repository = ContentImportRepository(engine)
    result = ContentIngestionEngine(engine).import_upload(
        _principal(), filename=filename, content=content, dry_run=dry_run
    )
    report = repository.get(_principal(), UUID(result.import_id))
    return report, repository


def _stage_failures(report: Any, selected: set[str]) -> list[dict[str, object]]:
    failures: list[dict[str, object]] = []
    for item in report.items:
        for stage in item.stages:
            if stage.stage in selected and stage.status in {"failed", "warning"}:
                failures.append(
                    {
                        "external_id": item.external_id,
                        "stage": stage.stage,
                        "status": stage.status,
                        "findings": stage.findings,
                        "metrics": stage.metrics,
                    }
                )
    return failures


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="content", description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    validate = commands.add_parser("validate", help="Run the complete pipeline without writes")
    validate.add_argument("path")
    importer = commands.add_parser("import", help="Import complete packages as reviewable drafts")
    importer.add_argument("path")
    importer.add_argument("--dry-run", action="store_true")
    for name in ("check-duplicates", "execute-solutions", "validate-rights"):
        command = commands.add_parser(name)
        command.add_argument("path")
    sync = commands.add_parser("sync-postgres", help="Import packages into PostgreSQL")
    sync.add_argument("path")
    report = commands.add_parser("report", help="Print a durable import report")
    report.add_argument("import_id", type=UUID)
    rollback = commands.add_parser(
        "rollback", help="Rollback unreviewed versions created by an import"
    )
    rollback.add_argument("import_id", type=UUID)
    return parser


def main() -> int:
    arguments = build_parser().parse_args()
    try:
        if arguments.command in {
            "validate",
            "import",
            "check-duplicates",
            "execute-solutions",
            "validate-rights",
            "sync-postgres",
        }:
            dry_run = arguments.command != "sync-postgres" and (
                arguments.command != "import" or arguments.dry_run
            )
            report, _ = _import_path(arguments.path, dry_run=dry_run)
            if arguments.command == "check-duplicates":
                findings = _stage_failures(report, {"duplicate_detection", "semantic_similarity"})
                _dump({"import_id": report.import_id, "findings": findings})
                return int(any(item["status"] == "failed" for item in findings))
            if arguments.command == "execute-solutions":
                findings = _stage_failures(report, {"executable_solution_validation"})
                _dump({"import_id": report.import_id, "findings": findings})
                return int(bool(findings))
            if arguments.command == "validate-rights":
                findings = _stage_failures(report, {"provenance_validation", "license_validation"})
                _dump({"import_id": report.import_id, "findings": findings})
                return int(bool(findings))
            _dump(report)
            return int(report.rejected_count > 0)

        engine = create_database_engine(Settings())
        repository = ContentImportRepository(engine)
        if arguments.command == "report":
            _dump(repository.get(_principal(), arguments.import_id))
        else:
            _dump(repository.rollback(_principal(), arguments.import_id))
        return 0
    except IngestionError as exc:
        print(json.dumps({"error": exc.message, "status_code": exc.status_code}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
