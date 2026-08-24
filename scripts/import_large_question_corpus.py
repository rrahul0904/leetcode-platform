#!/usr/bin/env python3
"""Stream a governed large question corpus into the native knowledge bank.

The importer is deliberately fail-closed:

* a manifest never substitutes for a physical source file;
* the physical file SHA/row count are verified before completion;
* rows are processed in bounded chunks;
* duplicate IDs/fingerprints/concept identities are tracked on disk, not in a
  million-element Python set;
* imports never auto-publish or auto-create runnable runtime links;
* checkpoint state is persisted after each committed chunk.

Parquet support uses ``pyarrow`` when installed. JSONL support is stdlib-only and
is used by unit tests and emergency operator workflows.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import os
import re
import sqlite3
import tempfile
from collections.abc import Iterator, Mapping, Sequence
from contextlib import AbstractContextManager
from pathlib import Path
from typing import Any, cast
from uuid import UUID

from sqlalchemy import Connection, Engine, text

from rigor_api.config import get_settings
from rigor_api.database import create_database_engine
from rigor_api.knowledge_ingestion import SourceDisposition, slugify

REQUIRED_COLUMNS = (
    "question_id",
    "subject",
    "platform",
    "topic",
    "subtopic",
    "difficulty",
    "level",
    "question_type",
    "seniority",
    "industry",
    "business_context",
    "question_statement",
    "input_output_or_schema",
    "requirements",
    "constraints",
    "expected_approach",
    "solution",
    "explanation",
    "time_complexity",
    "space_complexity",
    "common_mistakes",
    "options",
    "correct_answer",
    "why_other_options_incorrect",
    "tradeoffs",
    "best_practices",
    "tags",
    "content_fingerprint",
)

CLASSIFICATIONS = {
    "canonical_candidate",
    "legitimate_variant",
    "near_concept_duplicate",
    "reference_only",
    "runnable_candidate",
    "review_required",
    "rejected_quarantined",
}
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
JsonObject = dict[str, object]


class LargeCorpusError(ValueError):
    pass


class DuplicateTracker(AbstractContextManager["DuplicateTracker"]):
    """Disk-backed uniqueness tracker so validation memory stays bounded."""

    def __init__(self) -> None:
        handle = tempfile.NamedTemporaryFile(prefix="rigor-corpus-", suffix=".sqlite3", delete=False)
        handle.close()
        self.path = Path(handle.name)
        self.connection = sqlite3.connect(self.path)
        self.connection.executescript(
            """
            PRAGMA journal_mode=OFF;
            PRAGMA synchronous=OFF;
            CREATE TABLE ids (value TEXT PRIMARY KEY);
            CREATE TABLE fingerprints (value TEXT PRIMARY KEY);
            CREATE TABLE concepts (value TEXT PRIMARY KEY);
            """
        )

    def _insert_unique(self, table: str, value: str) -> bool:
        cursor = self.connection.execute(
            f"INSERT OR IGNORE INTO {table} (value) VALUES (?)",  # noqa: S608
            (value,),
        )
        return cursor.rowcount == 1

    def add_id(self, value: str) -> bool:
        return self._insert_unique("ids", value)

    def add_fingerprint(self, value: str) -> bool:
        return self._insert_unique("fingerprints", value)

    def add_concept(self, value: str) -> bool:
        return self._insert_unique("concepts", value)

    def close(self) -> None:
        try:
            self.connection.close()
        finally:
            self.path.unlink(missing_ok=True)

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        del exc_type, exc, traceback
        self.close()


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def stable_hash(value: object) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def required_text(row: Mapping[str, object], field: str) -> str:
    value = row.get(field)
    if value is None:
        raise LargeCorpusError(f"{field} is required")
    normalized = str(value).strip()
    if not normalized:
        raise LargeCorpusError(f"{field} is required")
    return normalized


def optional_text(row: Mapping[str, object], field: str) -> str | None:
    value = row.get(field)
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def string_list(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, tuple):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        text_value = value.strip()
        if not text_value:
            return []
        if text_value.startswith("["):
            try:
                decoded: object = json.loads(text_value)
            except json.JSONDecodeError:
                decoded = None
            if isinstance(decoded, list):
                return [str(item).strip() for item in decoded if str(item).strip()]
        return [item.strip() for item in text_value.split("|") if item.strip()]
    return [str(value).strip()]


def normalized_difficulty(value: object) -> str | None:
    normalized = str(value or "").strip().casefold()
    aliases = {
        "easy": "easy",
        "medium": "medium",
        "hard": "hard",
        "expert": "hard",
        "foundational": "easy",
        "intermediate": "medium",
        "advanced": "hard",
    }
    return aliases.get(normalized)


def concept_identity(row: Mapping[str, object]) -> str:
    """A conservative deterministic family key, not a semantic-uniqueness claim."""

    dimensions = {
        "subject": str(row.get("subject") or "").strip().casefold(),
        "platform": str(row.get("platform") or "").strip().casefold(),
        "topic": str(row.get("topic") or "").strip().casefold(),
        "subtopic": str(row.get("subtopic") or "").strip().casefold(),
        "question_type": str(row.get("question_type") or "").strip().casefold(),
        "expected_approach": str(row.get("expected_approach") or "").strip().casefold(),
    }
    return stable_hash(dimensions)


def validate_row(row: Mapping[str, object]) -> None:
    missing = [field for field in REQUIRED_COLUMNS if field not in row]
    if missing:
        raise LargeCorpusError(f"missing required columns: {', '.join(missing)}")
    for field in ("question_id", "subject", "topic", "question_statement", "solution"):
        required_text(row, field)
    fingerprint = required_text(row, "content_fingerprint").casefold()
    if not SHA256_RE.fullmatch(fingerprint):
        raise LargeCorpusError("content_fingerprint must be a lowercase SHA-256 hex digest")


def classify_row(
    row: Mapping[str, object],
    *,
    disposition: SourceDisposition,
    concept_is_new: bool,
) -> str:
    del row
    if disposition is SourceDisposition.REJECTED_PROPRIETARY:
        return "rejected_quarantined"
    if disposition is SourceDisposition.EXTERNAL_REFERENCE_ONLY:
        return "reference_only"
    if disposition is SourceDisposition.RIGHTS_REVIEW_REQUIRED:
        return "review_required"
    return "canonical_candidate" if concept_is_new else "legitimate_variant"


def publication_state(disposition: SourceDisposition) -> tuple[str, str]:
    if disposition is SourceDisposition.HOSTABLE_LICENSED:
        return "draft", "awaiting_technical_review"
    if disposition is SourceDisposition.EXTERNAL_REFERENCE_ONLY:
        return "metadata_only", "rights_metadata_only"
    if disposition is SourceDisposition.REJECTED_PROPRIETARY:
        return "blocked", "rejected_for_rights_risk"
    return "draft", "rights_review_required"


def source_language(row: Mapping[str, object]) -> str:
    subject = str(row.get("subject") or "").casefold()
    question_type = str(row.get("question_type") or "").casefold()
    if "sql" in subject or "sql" in question_type:
        return "sql"
    if "python" in subject or "pyspark" in subject or "python" in question_type:
        return "python"
    return "text"


def iter_jsonl(path: Path, *, start_row: int = 1) -> Iterator[tuple[int, JsonObject]]:
    with path.open("r", encoding="utf-8") as stream:
        for row_number, line in enumerate(stream, 1):
            if row_number < start_row or not line.strip():
                continue
            try:
                value: object = json.loads(line)
            except json.JSONDecodeError as exc:
                raise LargeCorpusError(f"{path}:{row_number}: invalid JSON") from exc
            if not isinstance(value, dict):
                raise LargeCorpusError(f"{path}:{row_number}: expected a JSON object")
            yield row_number, cast(JsonObject, value)


def _parquet_file(path: Path) -> Any:
    try:
        module = importlib.import_module("pyarrow.parquet")
    except ModuleNotFoundError as exc:
        raise LargeCorpusError(
            "Parquet import requires pyarrow. Install pyarrow in the operator environment."
        ) from exc
    parquet_file = getattr(module, "ParquetFile", None)
    if parquet_file is None:
        raise LargeCorpusError("pyarrow.parquet.ParquetFile is unavailable")
    return parquet_file(path)


def parquet_row_count(path: Path) -> int:
    parquet_file = _parquet_file(path)
    return int(parquet_file.metadata.num_rows)


def iter_parquet(
    path: Path,
    *,
    start_row: int = 1,
    batch_size: int = 250,
) -> Iterator[tuple[int, JsonObject]]:
    parquet_file = _parquet_file(path)
    columns = set(str(name) for name in parquet_file.schema.names)
    missing = sorted(set(REQUIRED_COLUMNS) - columns)
    if missing:
        raise LargeCorpusError(f"Parquet schema is missing: {', '.join(missing)}")
    row_number = 0
    for record_batch in parquet_file.iter_batches(batch_size=batch_size):
        records: object = record_batch.to_pylist()
        if not isinstance(records, list):
            raise LargeCorpusError("Parquet batch did not decode to records")
        for item in records:
            row_number += 1
            if row_number < start_row:
                continue
            if not isinstance(item, dict):
                raise LargeCorpusError(f"{path}:{row_number}: expected an object")
            yield row_number, cast(JsonObject, item)


def iter_rows(
    path: Path,
    *,
    start_row: int = 1,
    batch_size: int = 250,
) -> Iterator[tuple[int, JsonObject]]:
    suffix = path.suffix.casefold()
    if suffix in {".jsonl", ".ndjson"}:
        yield from iter_jsonl(path, start_row=start_row)
        return
    if suffix == ".parquet":
        yield from iter_parquet(path, start_row=start_row, batch_size=batch_size)
        return
    raise LargeCorpusError(f"Unsupported corpus format: {suffix or '<none>'}")


def physical_row_count(path: Path) -> int:
    if path.suffix.casefold() == ".parquet":
        return parquet_row_count(path)
    if path.suffix.casefold() in {".jsonl", ".ndjson"}:
        count = 0
        with path.open("rb") as stream:
            for line in stream:
                if line.strip():
                    count += 1
        return count
    raise LargeCorpusError(f"Unsupported corpus format: {path.suffix}")


def load_manifest(path: Path | None) -> tuple[JsonObject | None, str | None]:
    if path is None:
        return None, None
    try:
        raw = path.read_bytes()
        value: object = json.loads(raw)
    except (OSError, json.JSONDecodeError) as exc:
        raise LargeCorpusError(f"Manifest is unavailable or invalid: {path}") from exc
    if not isinstance(value, dict):
        raise LargeCorpusError("Manifest root must be an object")
    return cast(JsonObject, value), hashlib.sha256(raw).hexdigest()


def manifest_file_entry(manifest: Mapping[str, object] | None, filename: str) -> JsonObject | None:
    if manifest is None:
        return None
    files = manifest.get("files")
    if not isinstance(files, list):
        return None
    for item in files:
        if isinstance(item, dict) and str(item.get("file") or "") == filename:
            return cast(JsonObject, item)
    return None


def verify_physical_source(
    path: Path,
    *,
    manifest: Mapping[str, object] | None,
) -> tuple[str, int, int | None]:
    if not path.is_file():
        raise LargeCorpusError(f"Physical corpus file not found: {path}")
    actual_sha = sha256_file(path)
    actual_rows = physical_row_count(path)
    expected_rows: int | None = None
    entry = manifest_file_entry(manifest, path.name)
    if manifest is not None and entry is None:
        raise LargeCorpusError(f"Manifest does not contain physical file {path.name}")
    if entry is not None:
        expected_sha = str(entry.get("sha256") or "").casefold()
        if expected_sha and expected_sha != actual_sha:
            raise LargeCorpusError(
                f"SHA mismatch for {path.name}: expected {expected_sha}, got {actual_sha}"
            )
        rows_value = entry.get("rows", entry.get("footer_rows_verified"))
        if isinstance(rows_value, int):
            expected_rows = rows_value
        elif rows_value is not None:
            expected_rows = int(str(rows_value))
        if expected_rows is not None and expected_rows != actual_rows:
            raise LargeCorpusError(
                f"row-count mismatch for {path.name}: expected {expected_rows}, got {actual_rows}"
            )
    return actual_sha, actual_rows, expected_rows


def _uuid(value: object) -> UUID:
    return UUID(str(value))


def ensure_source_file(
    connection: Connection,
    *,
    source_name: str,
    source_filename: str,
    source_sha256: str,
    byte_count: int,
    disposition: SourceDisposition,
    corpus_version: str,
) -> UUID:
    source_id = _uuid(
        connection.execute(
            text(
                """
                INSERT INTO knowledge_sources (
                    source_name, original_filename, archive_sha256,
                    disposition, source_metadata
                ) VALUES (
                    :source_name, :filename, :sha256, :disposition,
                    jsonb_build_object('ingestion', 'large-corpus', 'corpus_version', :version)
                )
                ON CONFLICT (source_name) DO UPDATE
                SET original_filename=EXCLUDED.original_filename,
                    archive_sha256=EXCLUDED.archive_sha256,
                    disposition=EXCLUDED.disposition,
                    source_metadata=EXCLUDED.source_metadata,
                    updated_at=CURRENT_TIMESTAMP
                RETURNING id
                """
            ),
            {
                "source_name": source_name,
                "filename": source_filename,
                "sha256": source_sha256,
                "disposition": disposition.value,
                "version": corpus_version,
            },
        ).scalar_one()
    )
    return _uuid(
        connection.execute(
            text(
                """
                INSERT INTO knowledge_source_files (
                    source_id, relative_path, sha256, byte_count, suffix,
                    classification, parse_status
                ) VALUES (
                    :source_id, :path, :sha256, :bytes, :suffix,
                    'large_corpus', 'available'
                )
                ON CONFLICT (source_id, relative_path, sha256) DO UPDATE
                SET byte_count=EXCLUDED.byte_count,
                    parse_status='available'
                RETURNING id
                """
            ),
            {
                "source_id": source_id,
                "path": source_filename,
                "sha256": source_sha256,
                "bytes": byte_count,
                "suffix": Path(source_filename).suffix.casefold(),
            },
        ).scalar_one()
    )


def ensure_batch(
    connection: Connection,
    *,
    corpus_name: str,
    corpus_version: str,
    batch_id: str,
    source_filename: str,
    source_sha256: str,
    manifest_sha256: str | None,
    expected_rows: int | None,
    physical_rows: int,
) -> tuple[UUID, int, str]:
    row = (
        connection.execute(
            text(
                """
                INSERT INTO knowledge_corpus_import_batches (
                    corpus_name, corpus_version, batch_id, source_filename,
                    source_sha256, manifest_sha256, expected_rows, physical_rows,
                    status, started_at
                ) VALUES (
                    :corpus_name, :corpus_version, :batch_id, :source_filename,
                    :source_sha256, :manifest_sha256, :expected_rows, :physical_rows,
                    'running', CURRENT_TIMESTAMP
                )
                ON CONFLICT (corpus_name, corpus_version, batch_id) DO UPDATE
                SET source_filename=EXCLUDED.source_filename,
                    source_sha256=EXCLUDED.source_sha256,
                    manifest_sha256=EXCLUDED.manifest_sha256,
                    expected_rows=EXCLUDED.expected_rows,
                    physical_rows=EXCLUDED.physical_rows,
                    status=CASE
                      WHEN knowledge_corpus_import_batches.status='completed'
                      THEN 'completed'
                      ELSE 'running'
                    END,
                    started_at=COALESCE(
                      knowledge_corpus_import_batches.started_at,
                      CURRENT_TIMESTAMP
                    ),
                    updated_at=CURRENT_TIMESTAMP
                RETURNING id, checkpoint_row, status
                """
            ),
            {
                "corpus_name": corpus_name,
                "corpus_version": corpus_version,
                "batch_id": batch_id,
                "source_filename": source_filename,
                "source_sha256": source_sha256,
                "manifest_sha256": manifest_sha256,
                "expected_rows": expected_rows,
                "physical_rows": physical_rows,
            },
        )
        .mappings()
        .one()
    )
    return _uuid(row["id"]), int(row["checkpoint_row"]), str(row["status"])


def _problem_title(row: Mapping[str, object]) -> str:
    statement = required_text(row, "question_statement")
    first_line = statement.splitlines()[0].strip()
    return first_line[:300] if first_line else required_text(row, "question_id")


def _topics(row: Mapping[str, object]) -> list[tuple[str, str]]:
    values = [
        (required_text(row, "topic"), "topic"),
        (str(row.get("subtopic") or "").strip(), "subtopic"),
    ]
    seen: set[str] = set()
    result: list[tuple[str, str]] = []
    for name, category in values:
        slug = slugify(name)
        if not slug or slug in seen:
            continue
        seen.add(slug)
        result.append((name, category))
    return result


def import_row(
    connection: Connection,
    *,
    row: Mapping[str, object],
    row_number: int,
    batch_db_id: UUID,
    source_file_id: UUID,
    source_filename: str,
    source_sha256: str,
    corpus_version: str,
    classification: str,
    disposition: SourceDisposition,
) -> UUID:
    if classification not in CLASSIFICATIONS:
        raise LargeCorpusError(f"invalid classification: {classification}")
    question_id = required_text(row, "question_id")
    fingerprint = required_text(row, "content_fingerprint").casefold()
    canonical_key = f"large:{corpus_version}:{question_id}"
    slug = f"large-{slugify(corpus_version)}-{slugify(question_id)}"
    publication_status, review_status = publication_state(disposition)
    problem_id = _uuid(
        connection.execute(
            text(
                """
                INSERT INTO knowledge_problems (
                    canonical_key, external_id, title, slug, summary, description,
                    input_format, constraints, difficulty, publication_status,
                    review_status, primary_language, source_metadata
                ) VALUES (
                    :canonical_key, :external_id, :title, :slug,
                    left(:description, 500), :description, :input_format,
                    CAST(:constraints AS jsonb), :difficulty, :publication_status,
                    :review_status, :primary_language,
                    CAST(:source_metadata AS jsonb)
                )
                ON CONFLICT (canonical_key) DO UPDATE
                SET title=EXCLUDED.title,
                    description=EXCLUDED.description,
                    input_format=EXCLUDED.input_format,
                    constraints=EXCLUDED.constraints,
                    difficulty=EXCLUDED.difficulty,
                    primary_language=EXCLUDED.primary_language,
                    source_metadata=EXCLUDED.source_metadata,
                    updated_at=CURRENT_TIMESTAMP
                RETURNING id
                """
            ),
            {
                "canonical_key": canonical_key,
                "external_id": question_id,
                "title": _problem_title(row),
                "slug": slug,
                "description": required_text(row, "question_statement"),
                "input_format": optional_text(row, "input_output_or_schema"),
                "constraints": json.dumps(string_list(row.get("constraints"))),
                "difficulty": normalized_difficulty(row.get("difficulty")),
                "publication_status": publication_status,
                "review_status": review_status,
                "primary_language": source_language(row),
                "source_metadata": canonical_json(
                    {
                        "source_kind": "large_corpus",
                        "corpus_version": corpus_version,
                        "source_file": source_filename,
                        "source_row": row_number,
                        "source_sha256": source_sha256,
                        "content_fingerprint": fingerprint,
                    }
                ),
            },
        ).scalar_one()
    )
    connection.execute(
        text(
            """
            INSERT INTO knowledge_problem_sources (
                problem_id, source_file_id, source_hash, source_path, disposition
            ) VALUES (
                :problem_id, :source_file_id, :source_hash, :source_path, :disposition
            )
            ON CONFLICT (problem_id, source_file_id) DO UPDATE
            SET source_hash=EXCLUDED.source_hash,
                source_path=EXCLUDED.source_path,
                disposition=EXCLUDED.disposition,
                observed_at=CURRENT_TIMESTAMP
            """
        ),
        {
            "problem_id": problem_id,
            "source_file_id": source_file_id,
            "source_hash": source_sha256,
            "source_path": source_filename,
            "disposition": disposition.value,
        },
    )
    metadata = {field: row.get(field) for field in REQUIRED_COLUMNS if field != "solution"}
    connection.execute(
        text(
            """
            INSERT INTO knowledge_problem_serving_metadata (
                problem_id, corpus_batch_id, source_question_id, source_row_number,
                corpus_version, content_fingerprint, canonical_classification,
                platform, subtopic, seniority, industry, business_context,
                original_metadata
            ) VALUES (
                :problem_id, :batch_id, :source_question_id, :source_row_number,
                :corpus_version, :fingerprint, :classification,
                :platform, :subtopic, :seniority, :industry, :business_context,
                CAST(:metadata AS jsonb)
            )
            ON CONFLICT (problem_id) DO UPDATE
            SET corpus_batch_id=EXCLUDED.corpus_batch_id,
                source_row_number=EXCLUDED.source_row_number,
                content_fingerprint=EXCLUDED.content_fingerprint,
                canonical_classification=EXCLUDED.canonical_classification,
                platform=EXCLUDED.platform,
                subtopic=EXCLUDED.subtopic,
                seniority=EXCLUDED.seniority,
                industry=EXCLUDED.industry,
                business_context=EXCLUDED.business_context,
                original_metadata=EXCLUDED.original_metadata,
                updated_at=CURRENT_TIMESTAMP
            """
        ),
        {
            "problem_id": problem_id,
            "batch_id": batch_db_id,
            "source_question_id": question_id,
            "source_row_number": row_number,
            "corpus_version": corpus_version,
            "fingerprint": fingerprint,
            "classification": classification,
            "platform": optional_text(row, "platform"),
            "subtopic": optional_text(row, "subtopic"),
            "seniority": optional_text(row, "seniority"),
            "industry": optional_text(row, "industry"),
            "business_context": optional_text(row, "business_context"),
            "metadata": canonical_json(metadata),
        },
    )
    for topic_name, category in _topics(row):
        topic_slug = slugify(topic_name)
        topic_id = _uuid(
            connection.execute(
                text(
                    """
                    INSERT INTO knowledge_topics (slug, name, category)
                    VALUES (:slug, :name, :category)
                    ON CONFLICT (slug) DO UPDATE
                    SET name=EXCLUDED.name,
                        updated_at=CURRENT_TIMESTAMP
                    RETURNING id
                    """
                ),
                {"slug": topic_slug, "name": topic_name[:200], "category": category},
            ).scalar_one()
        )
        connection.execute(
            text(
                """
                INSERT INTO knowledge_problem_topics (problem_id, topic_id, confidence, source)
                VALUES (:problem_id, :topic_id, 1.0, 'large-corpus')
                ON CONFLICT (problem_id, topic_id) DO NOTHING
                """
            ),
            {"problem_id": problem_id, "topic_id": topic_id},
        )

    # Store the supplied solution for review, but never mark it executable here.
    # Runnable status requires an independently verified authored runtime package.
    solution_text = required_text(row, "solution")
    solution_hash = hashlib.sha256(solution_text.encode("utf-8")).hexdigest()
    approach_id = _uuid(
        connection.execute(
            text(
                """
                INSERT INTO knowledge_solution_approaches (
                    problem_id, name, slug, explanation, time_complexity,
                    space_complexity, sequence_number
                ) VALUES (
                    :problem_id, 'Large-corpus supplied solution', 'large-corpus-solution',
                    :explanation, :time_complexity, :space_complexity, 1
                )
                ON CONFLICT (problem_id, slug) DO UPDATE
                SET explanation=EXCLUDED.explanation,
                    time_complexity=EXCLUDED.time_complexity,
                    space_complexity=EXCLUDED.space_complexity,
                    updated_at=CURRENT_TIMESTAMP
                RETURNING id
                """
            ),
            {
                "problem_id": problem_id,
                "explanation": optional_text(row, "explanation"),
                "time_complexity": optional_text(row, "time_complexity"),
                "space_complexity": optional_text(row, "space_complexity"),
            },
        ).scalar_one()
    )
    connection.execute(
        text(
            """
            INSERT INTO knowledge_solutions (
                approach_id, source_file_id, language, runtime, source_code,
                explanation, source_hash, is_executable, review_status
            ) VALUES (
                :approach_id, :source_file_id, :language, NULL, :source_code,
                :explanation, :source_hash, false, :review_status
            )
            ON CONFLICT (approach_id, language, source_hash) DO UPDATE
            SET source_code=EXCLUDED.source_code,
                explanation=EXCLUDED.explanation,
                is_executable=false,
                review_status=EXCLUDED.review_status,
                updated_at=CURRENT_TIMESTAMP
            """
        ),
        {
            "approach_id": approach_id,
            "source_file_id": source_file_id,
            "language": source_language(row),
            "source_code": solution_text,
            "explanation": optional_text(row, "explanation"),
            "source_hash": solution_hash,
            "review_status": review_status,
        },
    )
    return problem_id


def _update_batch(
    connection: Connection,
    batch_db_id: UUID,
    *,
    checkpoint_row: int,
    status: str,
    counters: Mapping[str, int],
    failures: Sequence[Mapping[str, object]],
) -> None:
    connection.execute(
        text(
            """
            UPDATE knowledge_corpus_import_batches
            SET checkpoint_row=:checkpoint_row,
                status=:status,
                counters=CAST(:counters AS jsonb),
                failure_summary=CAST(:failures AS jsonb),
                completed_at=CASE WHEN :status='completed' THEN CURRENT_TIMESTAMP ELSE NULL END,
                updated_at=CURRENT_TIMESTAMP
            WHERE id=:batch_id
            """
        ),
        {
            "batch_id": batch_db_id,
            "checkpoint_row": checkpoint_row,
            "status": status,
            "counters": canonical_json(dict(counters)),
            "failures": canonical_json(list(failures)[-100:]),
        },
    )


def process_source(
    engine: Engine,
    *,
    source_path: Path,
    manifest: Mapping[str, object] | None,
    manifest_sha256: str | None,
    corpus_name: str,
    corpus_version: str,
    batch_id: str,
    disposition: SourceDisposition,
    chunk_size: int,
    dry_run: bool,
) -> dict[str, object]:
    source_sha, physical_rows, expected_rows = verify_physical_source(
        source_path,
        manifest=manifest,
    )
    counters: dict[str, int] = {
        "physical_source_rows": physical_rows,
        "parsed": 0,
        "validated": 0,
        "rejected": 0,
        "duplicate_ids": 0,
        "duplicate_fingerprints": 0,
        "canonical": 0,
        "variants": 0,
        "near_duplicates": 0,
        "review_required": 0,
        "reference_only": 0,
        "runnable_candidates": 0,
        "published": 0,
        "runtime_verified": 0,
    }
    failures: list[dict[str, object]] = []

    with engine.begin() as connection:
        batch_db_id, checkpoint, existing_status = ensure_batch(
            connection,
            corpus_name=corpus_name,
            corpus_version=corpus_version,
            batch_id=batch_id,
            source_filename=source_path.name,
            source_sha256=source_sha,
            manifest_sha256=manifest_sha256,
            expected_rows=expected_rows,
            physical_rows=physical_rows,
        )
        if existing_status == "completed" and checkpoint == physical_rows and not dry_run:
            existing = connection.execute(
                text(
                    "SELECT counters FROM knowledge_corpus_import_batches WHERE id=:id"
                ),
                {"id": batch_db_id},
            ).scalar_one()
            return {
                "status": "already_imported",
                "batch_id": str(batch_db_id),
                "source_sha256": source_sha,
                "physical_rows": physical_rows,
                "counters": existing,
            }
        source_file_id = ensure_source_file(
            connection,
            source_name=f"{corpus_name}:{corpus_version}:{source_path.name}",
            source_filename=source_path.name,
            source_sha256=source_sha,
            byte_count=source_path.stat().st_size,
            disposition=disposition,
            corpus_version=corpus_version,
        )

    start_row = checkpoint + 1 if checkpoint > 0 and not dry_run else 1
    processed_since_commit = 0
    last_row = checkpoint
    with DuplicateTracker() as tracker:
        for row_number, row in iter_rows(
            source_path,
            start_row=1,
            batch_size=chunk_size,
        ):
            counters["parsed"] += 1
            try:
                validate_row(row)
                question_id = required_text(row, "question_id")
                fingerprint = required_text(row, "content_fingerprint").casefold()
                if not tracker.add_id(question_id):
                    counters["duplicate_ids"] += 1
                    counters["rejected"] += 1
                    continue
                if not tracker.add_fingerprint(fingerprint):
                    counters["duplicate_fingerprints"] += 1
                    counters["rejected"] += 1
                    continue
                concept_is_new = tracker.add_concept(concept_identity(row))
                classification = classify_row(
                    row,
                    disposition=disposition,
                    concept_is_new=concept_is_new,
                )
                counters["validated"] += 1
            except LargeCorpusError as exc:
                counters["rejected"] += 1
                if len(failures) < 100:
                    failures.append({"row": row_number, "error": str(exc)})
                continue

            if classification == "canonical_candidate":
                counters["canonical"] += 1
            elif classification == "legitimate_variant":
                counters["variants"] += 1
            elif classification == "near_concept_duplicate":
                counters["near_duplicates"] += 1
            elif classification == "review_required":
                counters["review_required"] += 1
            elif classification == "reference_only":
                counters["reference_only"] += 1
            elif classification == "runnable_candidate":
                counters["runnable_candidates"] += 1

            if row_number < start_row:
                continue
            if dry_run:
                last_row = row_number
                continue

            with engine.begin() as connection:
                import_row(
                    connection,
                    row=row,
                    row_number=row_number,
                    batch_db_id=batch_db_id,
                    source_file_id=source_file_id,
                    source_filename=source_path.name,
                    source_sha256=source_sha,
                    corpus_version=corpus_version,
                    classification=classification,
                    disposition=disposition,
                )
                last_row = row_number
                processed_since_commit += 1
                if processed_since_commit >= chunk_size:
                    _update_batch(
                        connection,
                        batch_db_id,
                        checkpoint_row=last_row,
                        status="running",
                        counters=counters,
                        failures=failures,
                    )
                    processed_since_commit = 0

    if counters["parsed"] != physical_rows:
        raise LargeCorpusError(
            f"streamed {counters['parsed']} physical rows but file reports {physical_rows}"
        )
    terminal_status = "validated" if dry_run else "completed"
    if not dry_run:
        with engine.begin() as connection:
            _update_batch(
                connection,
                batch_db_id,
                checkpoint_row=physical_rows,
                status="completed",
                counters=counters,
                failures=failures,
            )
    return {
        "status": terminal_status,
        "batch_id": str(batch_db_id),
        "source_sha256": source_sha,
        "physical_rows": physical_rows,
        "expected_rows": expected_rows,
        "counters": counters,
        "failures": failures,
    }


def _disposition(value: str) -> SourceDisposition:
    try:
        return SourceDisposition(value)
    except ValueError as exc:
        allowed = ", ".join(item.value for item in SourceDisposition)
        raise LargeCorpusError(f"Unsupported disposition {value!r}; expected one of {allowed}") from exc


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--corpus-name", default="large-technical-question-bank")
    parser.add_argument("--corpus-version", required=True)
    parser.add_argument("--batch-id")
    parser.add_argument("--chunk-size", type=int, default=250)
    parser.add_argument("--database-url", default=os.getenv("RIGOR_DATABASE_URL"))
    parser.add_argument(
        "--disposition",
        default=SourceDisposition.RIGHTS_REVIEW_REQUIRED.value,
        choices=[item.value for item in SourceDisposition],
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if args.chunk_size < 10 or args.chunk_size > 5_000:
        raise SystemExit("--chunk-size must be between 10 and 5000")

    manifest, manifest_sha = load_manifest(args.manifest)
    settings = get_settings()
    database_url = args.database_url or settings.database_url
    engine = create_database_engine(settings, database_url)
    try:
        result = process_source(
            engine,
            source_path=args.source,
            manifest=manifest,
            manifest_sha256=manifest_sha,
            corpus_name=args.corpus_name,
            corpus_version=args.corpus_version,
            batch_id=args.batch_id or args.source.stem,
            disposition=_disposition(args.disposition),
            chunk_size=args.chunk_size,
            dry_run=args.dry_run,
        )
    finally:
        engine.dispose()
    print(json.dumps(result, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
