#!/usr/bin/env python3
"""Stream a governed large question corpus into Rigor's native knowledge bank.

This importer is intentionally fail-closed. It verifies the physical file before
completion, never treats a manifest as a substitute for source bytes, processes
records in bounded chunks, keeps global duplicate tracking on disk, checkpoints
restart state, and never auto-publishes or auto-creates runnable runtime links.

Parquet support uses ``pyarrow`` when it is installed in the operator
environment. JSONL support is stdlib-only and is also used by the unit tests.
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
from dataclasses import dataclass
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
SAFE_REFERENCE_FIELDS = (
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
    "tags",
    "content_fingerprint",
)
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
JsonObject = dict[str, object]


class LargeCorpusError(ValueError):
    pass


@dataclass(frozen=True)
class PreparedRow:
    row_number: int
    row: JsonObject
    classification: str


class DuplicateTracker:
    """Disk-backed uniqueness/family tracker so million-row validation is bounded."""

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

    def __enter__(self) -> DuplicateTracker:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: object,
    ) -> None:
        del exc_type, exc_value, traceback
        self.close()

    def _insert_unique(self, table: str, value: str) -> bool:
        # table is chosen only by the three fixed methods below.
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


def canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def stable_hash(value: object) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def required_text(row: Mapping[str, object], field: str) -> str:
    value = row.get(field)
    normalized = "" if value is None else str(value).strip()
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
    if isinstance(value, (list, tuple)):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return []
        if stripped.startswith("["):
            try:
                decoded: object = json.loads(stripped)
            except json.JSONDecodeError:
                decoded = None
            if isinstance(decoded, list):
                return [str(item).strip() for item in decoded if str(item).strip()]
        return [item.strip() for item in stripped.split("|") if item.strip()]
    return [str(value).strip()]


def normalized_difficulty(value: object) -> str | None:
    aliases = {
        "easy": "easy",
        "medium": "medium",
        "hard": "hard",
        "expert": "hard",
        "foundational": "easy",
        "intermediate": "medium",
        "advanced": "hard",
    }
    return aliases.get(str(value or "").strip().casefold())


def concept_identity(row: Mapping[str, object]) -> str:
    """Conservative family key; this is not a semantic-uniqueness claim."""
    return stable_hash(
        {
            "subject": str(row.get("subject") or "").strip().casefold(),
            "platform": str(row.get("platform") or "").strip().casefold(),
            "topic": str(row.get("topic") or "").strip().casefold(),
            "subtopic": str(row.get("subtopic") or "").strip().casefold(),
            "question_type": str(row.get("question_type") or "").strip().casefold(),
            "expected_approach": str(row.get("expected_approach") or "").strip().casefold(),
        }
    )


def validate_row(row: Mapping[str, object]) -> None:
    missing = [field for field in REQUIRED_COLUMNS if field not in row]
    if missing:
        raise LargeCorpusError(f"missing required columns: {', '.join(missing)}")
    for field in ("question_id", "subject", "topic", "question_statement", "solution"):
        required_text(row, field)
    fingerprint = required_text(row, "content_fingerprint").casefold()
    if not SHA256_RE.fullmatch(fingerprint):
        raise LargeCorpusError("content_fingerprint must be a lowercase SHA-256 hex digest")


def canonical_classification(
    *,
    disposition: SourceDisposition,
    concept_is_new: bool,
) -> str:
    if disposition is SourceDisposition.REJECTED_PROPRIETARY:
        return "rejected_quarantined"
    if disposition is SourceDisposition.EXTERNAL_REFERENCE_ONLY:
        return "reference_only"
    # Rights review is tracked independently. It must not destroy family identity.
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


def iter_jsonl(path: Path) -> Iterator[tuple[int, JsonObject]]:
    with path.open("r", encoding="utf-8") as stream:
        for row_number, line in enumerate(stream, 1):
            if not line.strip():
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
            "Parquet import requires pyarrow in the operator environment"
        ) from exc
    parquet_file = getattr(module, "ParquetFile", None)
    if parquet_file is None:
        raise LargeCorpusError("pyarrow.parquet.ParquetFile is unavailable")
    return parquet_file(path)


def parquet_row_count(path: Path) -> int:
    parquet_file = _parquet_file(path)
    return int(parquet_file.metadata.num_rows)


def iter_parquet(path: Path, *, batch_size: int) -> Iterator[tuple[int, JsonObject]]:
    parquet_file = _parquet_file(path)
    columns = {str(name) for name in parquet_file.schema.names}
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
            if not isinstance(item, dict):
                raise LargeCorpusError(f"{path}:{row_number}: expected an object")
            yield row_number, cast(JsonObject, item)


def iter_rows(path: Path, *, batch_size: int) -> Iterator[tuple[int, JsonObject]]:
    suffix = path.suffix.casefold()
    if suffix in {".jsonl", ".ndjson"}:
        yield from iter_jsonl(path)
    elif suffix == ".parquet":
        yield from iter_parquet(path, batch_size=batch_size)
    else:
        raise LargeCorpusError(f"Unsupported corpus format: {suffix or '<none>'}")


def physical_row_count(path: Path) -> int:
    if path.suffix.casefold() == ".parquet":
        return parquet_row_count(path)
    if path.suffix.casefold() in {".jsonl", ".ndjson"}:
        with path.open("rb") as stream:
            return sum(1 for line in stream if line.strip())
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
        if rows_value is not None:
            expected_rows = int(str(rows_value))
            if expected_rows != actual_rows:
                raise LargeCorpusError(
                    f"row-count mismatch for {path.name}: "
                    f"expected {expected_rows}, got {actual_rows}"
                )
    return actual_sha, actual_rows, expected_rows


def initial_counters(physical_rows: int) -> dict[str, int]:
    return {
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


def prepare_stream(
    path: Path,
    *,
    batch_size: int,
    disposition: SourceDisposition,
    counters: dict[str, int],
    failures: list[dict[str, object]],
) -> Iterator[PreparedRow]:
    with DuplicateTracker() as tracker:
        for row_number, row in iter_rows(path, batch_size=batch_size):
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
                classification = canonical_classification(
                    disposition=disposition,
                    concept_is_new=concept_is_new,
                )
                counters["validated"] += 1
            except LargeCorpusError as exc:
                counters["rejected"] += 1
                if len(failures) < 100:
                    failures.append({"row": row_number, "error": str(exc)})
                continue

            if disposition is SourceDisposition.RIGHTS_REVIEW_REQUIRED:
                counters["review_required"] += 1
            if classification == "canonical_candidate":
                counters["canonical"] += 1
            elif classification == "legitimate_variant":
                counters["variants"] += 1
            elif classification == "reference_only":
                counters["reference_only"] += 1
            elif classification == "rejected_quarantined":
                counters["rejected"] += 1
            yield PreparedRow(row_number=row_number, row=row, classification=classification)


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
                      THEN 'completed' ELSE 'running' END,
                    started_at=COALESCE(
                      knowledge_corpus_import_batches.started_at, CURRENT_TIMESTAMP
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


def problem_title(row: Mapping[str, object], disposition: SourceDisposition) -> str:
    if disposition is SourceDisposition.EXTERNAL_REFERENCE_ONLY:
        topic = required_text(row, "topic")
        return f"{topic}: {required_text(row, 'question_id')}"[:500]
    statement = required_text(row, "question_statement")
    first_line = statement.splitlines()[0].strip()
    return (first_line or required_text(row, "question_id"))[:500]


def topic_pairs(row: Mapping[str, object]) -> list[tuple[str, str]]:
    values = [
        (required_text(row, "topic"), "topic"),
        (str(row.get("subtopic") or "").strip(), "subtopic"),
    ]
    seen: set[str] = set()
    result: list[tuple[str, str]] = []
    for name, category in values:
        topic_slug = slugify(name)
        if topic_slug and topic_slug not in seen:
            seen.add(topic_slug)
            result.append((name, category))
    return result


def import_row(
    connection: Connection,
    *,
    prepared: PreparedRow,
    batch_db_id: UUID,
    source_file_id: UUID,
    source_filename: str,
    source_sha256: str,
    corpus_version: str,
    disposition: SourceDisposition,
) -> None:
    row = prepared.row
    if prepared.classification == "rejected_quarantined":
        return
    question_id = required_text(row, "question_id")
    fingerprint = required_text(row, "content_fingerprint").casefold()
    canonical_key = f"large:{corpus_version}:{question_id}"
    problem_slug = f"large-{slugify(corpus_version)}-{slugify(question_id)}"[:500]
    publication_status, review_status = publication_state(disposition)
    may_store_body = disposition is not SourceDisposition.EXTERNAL_REFERENCE_ONLY
    description = required_text(row, "question_statement") if may_store_body else None
    input_format = optional_text(row, "input_output_or_schema") if may_store_body else None
    constraints = string_list(row.get("constraints")) if may_store_body else []
    source_metadata = {
        "source_kind": "large_corpus",
        "corpus_version": corpus_version,
        "source_file": source_filename,
        "source_row": prepared.row_number,
        "source_sha256": source_sha256,
        "content_fingerprint": fingerprint,
    }
    original_metadata = {
        field: row.get(field)
        for field in (REQUIRED_COLUMNS if may_store_body else SAFE_REFERENCE_FIELDS)
        if field != "solution"
    }
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
                    left(COALESCE(:description, :title), 500), :description,
                    :input_format, CAST(:constraints AS jsonb), :difficulty,
                    :publication_status, :review_status, :primary_language,
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
                "title": problem_title(row, disposition),
                "slug": problem_slug,
                "description": description,
                "input_format": input_format,
                "constraints": json.dumps(constraints),
                "difficulty": normalized_difficulty(row.get("difficulty")),
                "publication_status": publication_status,
                "review_status": review_status,
                "primary_language": source_language(row),
                "source_metadata": canonical_json(source_metadata),
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
            "source_row_number": prepared.row_number,
            "corpus_version": corpus_version,
            "fingerprint": fingerprint,
            "classification": prepared.classification,
            "platform": optional_text(row, "platform"),
            "subtopic": optional_text(row, "subtopic"),
            "seniority": optional_text(row, "seniority"),
            "industry": optional_text(row, "industry"),
            "business_context": optional_text(row, "business_context") if may_store_body else None,
            "metadata": canonical_json(original_metadata),
        },
    )
    for topic_name, category in topic_pairs(row):
        topic_slug = slugify(topic_name)
        topic_id = _uuid(
            connection.execute(
                text(
                    """
                    INSERT INTO knowledge_topics (slug, name, category)
                    VALUES (:slug, :name, :category)
                    ON CONFLICT (slug) DO UPDATE
                    SET name=EXCLUDED.name, updated_at=CURRENT_TIMESTAMP
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

    if not may_store_body:
        return
    # The supplied solution is review content only. It is never executable here;
    # verified runnable status comes only from knowledge_problem_runtime_links.
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


def update_batch(
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


def validate_source(
    source_path: Path,
    *,
    manifest: Mapping[str, object] | None,
    disposition: SourceDisposition,
    chunk_size: int,
) -> dict[str, object]:
    source_sha, physical_rows, expected_rows = verify_physical_source(
        source_path, manifest=manifest
    )
    counters = initial_counters(physical_rows)
    failures: list[dict[str, object]] = []
    for _prepared in prepare_stream(
        source_path,
        batch_size=chunk_size,
        disposition=disposition,
        counters=counters,
        failures=failures,
    ):
        pass
    if counters["parsed"] != physical_rows:
        raise LargeCorpusError(
            f"streamed {counters['parsed']} rows but physical metadata reports {physical_rows}"
        )
    return {
        "status": "validated",
        "source_sha256": source_sha,
        "physical_rows": physical_rows,
        "expected_rows": expected_rows,
        "counters": counters,
        "failures": failures,
    }


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
) -> dict[str, object]:
    source_sha, physical_rows, expected_rows = verify_physical_source(
        source_path, manifest=manifest
    )
    counters = initial_counters(physical_rows)
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
        source_file_id = ensure_source_file(
            connection,
            source_name=f"{corpus_name}:{corpus_version}:{source_path.name}",
            source_filename=source_path.name,
            source_sha256=source_sha,
            byte_count=source_path.stat().st_size,
            disposition=disposition,
            corpus_version=corpus_version,
        )
        if existing_status == "completed" and checkpoint == physical_rows:
            existing = connection.execute(
                text("SELECT counters FROM knowledge_corpus_import_batches WHERE id=:id"),
                {"id": batch_db_id},
            ).scalar_one()
            return {
                "status": "already_imported",
                "batch_id": str(batch_db_id),
                "source_sha256": source_sha,
                "physical_rows": physical_rows,
                "counters": existing,
            }

    pending: list[PreparedRow] = []
    last_physical_row = checkpoint
    rows_since_checkpoint = 0

    def flush(rows: list[PreparedRow], checkpoint_row: int, final: bool = False) -> None:
        with engine.begin() as connection:
            for prepared in rows:
                if prepared.row_number <= checkpoint:
                    continue
                import_row(
                    connection,
                    prepared=prepared,
                    batch_db_id=batch_db_id,
                    source_file_id=source_file_id,
                    source_filename=source_path.name,
                    source_sha256=source_sha,
                    corpus_version=corpus_version,
                    disposition=disposition,
                )
            update_batch(
                connection,
                batch_db_id,
                checkpoint_row=checkpoint_row,
                status="completed" if final else "running",
                counters=counters,
                failures=failures,
            )

    for prepared in prepare_stream(
        source_path,
        batch_size=chunk_size,
        disposition=disposition,
        counters=counters,
        failures=failures,
    ):
        last_physical_row = prepared.row_number
        rows_since_checkpoint += 1
        if prepared.row_number > checkpoint and prepared.classification != "rejected_quarantined":
            pending.append(prepared)
        if rows_since_checkpoint >= chunk_size:
            flush(pending, last_physical_row)
            pending = []
            rows_since_checkpoint = 0

    # Rejected/duplicate physical rows are not yielded by prepare_stream. The
    # authoritative completion checkpoint is therefore the verified physical row
    # count after the full stream has been consumed.
    if counters["parsed"] != physical_rows:
        raise LargeCorpusError(
            f"streamed {counters['parsed']} rows but physical metadata reports {physical_rows}"
        )
    flush(pending, physical_rows, final=True)
    return {
        "status": "completed",
        "batch_id": str(batch_db_id),
        "source_sha256": source_sha,
        "physical_rows": physical_rows,
        "expected_rows": expected_rows,
        "counters": counters,
        "failures": failures,
    }


def parse_disposition(value: str) -> SourceDisposition:
    try:
        return SourceDisposition(value)
    except ValueError as exc:
        allowed = ", ".join(item.value for item in SourceDisposition)
        raise LargeCorpusError(f"Unsupported disposition {value!r}; expected {allowed}") from exc


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
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()
    if args.chunk_size < 10 or args.chunk_size > 5_000:
        raise SystemExit("--chunk-size must be between 10 and 5000")
    manifest, manifest_sha = load_manifest(args.manifest)
    disposition = parse_disposition(args.disposition)

    if args.validate_only:
        result = validate_source(
            args.source,
            manifest=manifest,
            disposition=disposition,
            chunk_size=args.chunk_size,
        )
    else:
        settings = get_settings()
        database_url = args.database_url or settings.operational_database_url or settings.database_url
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
                disposition=disposition,
                chunk_size=args.chunk_size,
            )
        finally:
            engine.dispose()
    print(json.dumps(result, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
