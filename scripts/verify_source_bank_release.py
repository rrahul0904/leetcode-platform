#!/usr/bin/env python3
"""Prove the reviewed source-backed corpus against a real PostgreSQL database."""

from __future__ import annotations

import argparse
import base64
import binascii
import hashlib
import json
import os
from collections.abc import Mapping
from pathlib import Path

from sqlalchemy import Connection, text

from import_source_backed_question_bank import (
    DEFAULT_ARCHIVE,
    load_payload,
    validate_payload,
)
from rigor_api.config import get_settings
from rigor_api.database import create_database_engine
from rigor_api.knowledge_store import import_knowledge_payload

REVIEWED_ARCHIVE_SHA256 = (
    "9236110b4c4af1547455998e96f100ce5d2ba945bba1fd02d9194714a11a873b"
)
EXPECTED_DATABASE_COUNTS = {
    "searchable_questions": 3425,
    "company_questions": 3424,
    "company_associations": 35348,
    "statement_backed": 121,
    "reference_solutions": 120,
    "system_design_resources": 29,
}
SOURCE_NAME = "uploaded-source-backed-question-bank"


class ReleaseVerificationError(RuntimeError):
    """Raised when the installed corpus differs from reviewed release evidence."""


def _archive_sha256(path: Path) -> str:
    encoded = "".join(path.read_text(encoding="ascii").split())
    try:
        payload = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError) as error:
        raise ReleaseVerificationError(f"{path} is not valid base64") from error
    return hashlib.sha256(payload).hexdigest()


def _required_string(mapping: Mapping[str, object], key: str) -> str:
    value = mapping.get(key)
    if not isinstance(value, str) or not value:
        raise ReleaseVerificationError(f"import result is missing {key}")
    return value


def _expect(label: str, actual: object, expected: object) -> None:
    if actual != expected:
        raise ReleaseVerificationError(
            f"{label}: expected {expected!r}, found {actual!r}"
        )


def _scalar_int(
    connection: Connection,
    statement: str,
    parameters: Mapping[str, object] | None = None,
) -> int:
    value = connection.execute(text(statement), dict(parameters or {})).scalar_one()
    return int(value)


def _database_counts(connection: Connection) -> dict[str, int]:
    return {
        "searchable_questions": _scalar_int(
            connection,
            """
            SELECT count(*)
            FROM knowledge_problems
            WHERE deleted_at IS NULL
              AND publication_status IN ('published', 'metadata_only')
            """,
        ),
        "company_questions": _scalar_int(
            connection,
            "SELECT count(DISTINCT problem_id) FROM knowledge_company_observations",
        ),
        "company_associations": _scalar_int(
            connection,
            "SELECT count(*) FROM knowledge_company_observations",
        ),
        "statement_backed": _scalar_int(
            connection,
            """
            SELECT count(*)
            FROM knowledge_problems
            WHERE deleted_at IS NULL
              AND NULLIF(btrim(description), '') IS NOT NULL
            """,
        ),
        "reference_solutions": _scalar_int(
            connection,
            "SELECT count(*) FROM knowledge_solutions",
        ),
        "system_design_resources": _scalar_int(
            connection,
            "SELECT count(*) FROM knowledge_system_design_articles",
        ),
    }


def _duplicate_counts(connection: Connection) -> dict[str, int]:
    return {
        "problems": _scalar_int(
            connection,
            """
            SELECT COALESCE(sum(row_count - 1), 0)
            FROM (
                SELECT count(*) AS row_count
                FROM knowledge_problems
                GROUP BY canonical_key
                HAVING count(*) > 1
            ) AS duplicates
            """,
        ),
        "company_associations": _scalar_int(
            connection,
            """
            SELECT COALESCE(sum(row_count - 1), 0)
            FROM (
                SELECT count(*) AS row_count
                FROM knowledge_company_observations
                GROUP BY problem_id, company_id
                HAVING count(*) > 1
            ) AS duplicates
            """,
        ),
        "system_design": _scalar_int(
            connection,
            """
            SELECT COALESCE(sum(row_count - 1), 0)
            FROM (
                SELECT count(*) AS row_count
                FROM knowledge_system_design_articles
                GROUP BY slug
                HAVING count(*) > 1
            ) AS duplicates
            """,
        ),
    }


def verify_release(archive: Path, database_url: str) -> dict[str, object]:
    reviewed_sha = _archive_sha256(archive)
    _expect("reviewed normalized archive SHA-256", reviewed_sha, REVIEWED_ARCHIVE_SHA256)

    payload = load_payload(archive)
    payload_counts = validate_payload(payload)
    settings = get_settings()
    engine = create_database_engine(settings, database_url)
    try:
        first = import_knowledge_payload(engine, payload)
        _expect("first import status", first.get("status"), "completed")
        first_corpus_sha = _required_string(first, "corpus_sha256")

        second = import_knowledge_payload(engine, payload)
        _expect("second import status", second.get("status"), "already_imported")
        _expect(
            "repeat import corpus identity",
            second.get("corpus_sha256"),
            first_corpus_sha,
        )

        with engine.connect() as connection:
            database_counts = _database_counts(connection)
            duplicate_counts = _duplicate_counts(connection)
            canonical_import_records = _scalar_int(
                connection,
                """
                SELECT count(*)
                FROM knowledge_import_runs AS run
                JOIN knowledge_sources AS source ON source.id = run.source_id
                WHERE source.source_name = :source_name
                  AND run.corpus_sha256 = :corpus_sha256
                  AND run.status = 'completed'
                """,
                {
                    "source_name": SOURCE_NAME,
                    "corpus_sha256": first_corpus_sha,
                },
            )
    finally:
        engine.dispose()

    for key, expected in EXPECTED_DATABASE_COUNTS.items():
        _expect(f"database count {key}", database_counts[key], expected)
    _expect("canonical corpus import records", canonical_import_records, 1)
    for key, count in duplicate_counts.items():
        _expect(f"duplicate {key}", count, 0)

    return {
        "status": "passed",
        "reviewed_archive_sha256": reviewed_sha,
        "first_import": {
            "status": first["status"],
            "corpus_sha256": first_corpus_sha,
        },
        "repeat_import": {
            "status": second["status"],
            "corpus_sha256": second["corpus_sha256"],
        },
        "payload_counts": payload_counts,
        "database_counts": database_counts,
        "canonical_import_records": canonical_import_records,
        "duplicate_rows": duplicate_counts,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--archive", type=Path, default=DEFAULT_ARCHIVE)
    parser.add_argument("--database-url", default=os.getenv("RIGOR_DATABASE_URL"))
    args = parser.parse_args()

    settings = get_settings()
    database_url = (
        args.database_url or settings.operational_database_url or settings.database_url
    )
    result = verify_release(args.archive, database_url)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
