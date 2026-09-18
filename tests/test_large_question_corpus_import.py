from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from rigor_api.knowledge_ingestion import SourceDisposition
from scripts.import_large_question_corpus import (
    LargeCorpusError,
    REQUIRED_COLUMNS,
    canonical_classification,
    load_manifest,
    sha256_file,
    stable_hash,
    validate_source,
    verify_physical_source,
)


def _row(question_id: str, *, family: str = "window-functions") -> dict[str, object]:
    row: dict[str, object] = {field: "value" for field in REQUIRED_COLUMNS}
    row.update(
        {
            "question_id": question_id,
            "subject": "SQL",
            "platform": "PostgreSQL",
            "topic": "SQL Optimization",
            "subtopic": family,
            "difficulty": "Hard",
            "level": "Senior",
            "question_type": "sql_coding",
            "seniority": "Senior / Staff",
            "industry": "SaaS",
            "business_context": "Investigate a warehouse workload regression.",
            "question_statement": f"Diagnose query regression {question_id}.",
            "input_output_or_schema": "orders(id bigint, customer_id bigint)",
            "requirements": "Return a deterministic result.",
            "constraints": '["10M rows", "p95 under 2s"]',
            "expected_approach": "inspect plan and reduce scanned rows",
            "solution": "SELECT customer_id, count(*) FROM orders GROUP BY customer_id;",
            "explanation": "Inspect the plan before optimizing.",
            "time_complexity": "O(n)",
            "space_complexity": "O(k)",
            "common_mistakes": "optimizing without an execution plan",
            "options": "[]",
            "correct_answer": "n/a",
            "why_other_options_incorrect": "n/a",
            "tradeoffs": "index maintenance versus read latency",
            "best_practices": "measure before and after",
            "tags": '["sql", "performance"]',
        }
    )
    row["content_fingerprint"] = stable_hash(
        {
            "id": question_id,
            "statement": row["question_statement"],
            "family": family,
        }
    )
    return row


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def _manifest(path: Path, source: Path, rows: int) -> Path:
    payload = {
        "dataset": "test",
        "files": [
            {
                "file": source.name,
                "rows": rows,
                "sha256": sha256_file(source),
            }
        ],
    }
    path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
    return path


def test_validate_source_reports_physical_facts_without_database(tmp_path: Path) -> None:
    source = tmp_path / "questions.jsonl"
    _write_jsonl(source, [_row("Q-001"), _row("Q-002", family="joins")])
    manifest_path = _manifest(tmp_path / "manifest.json", source, 2)
    manifest, _manifest_sha = load_manifest(manifest_path)

    result = validate_source(
        source,
        manifest=manifest,
        disposition=SourceDisposition.RIGHTS_REVIEW_REQUIRED,
        chunk_size=10,
    )

    assert result["status"] == "validated"
    assert result["physical_rows"] == 2
    counters = result["counters"]
    assert isinstance(counters, dict)
    assert counters["parsed"] == 2
    assert counters["validated"] == 2
    assert counters["review_required"] == 2
    assert counters["published"] == 0
    assert counters["runtime_verified"] == 0


def test_duplicate_ids_and_fingerprints_are_rejected_deterministically(tmp_path: Path) -> None:
    first = _row("Q-001")
    duplicate_id = _row("Q-001", family="joins")
    duplicate_fingerprint = _row("Q-003", family="aggregations")
    duplicate_fingerprint["content_fingerprint"] = first["content_fingerprint"]
    source = tmp_path / "questions.jsonl"
    _write_jsonl(source, [first, duplicate_id, duplicate_fingerprint])

    result = validate_source(
        source,
        manifest=None,
        disposition=SourceDisposition.HOSTABLE_LICENSED,
        chunk_size=10,
    )
    counters = result["counters"]
    assert isinstance(counters, dict)
    assert counters["physical_source_rows"] == 3
    assert counters["duplicate_ids"] == 1
    assert counters["duplicate_fingerprints"] == 1
    assert counters["rejected"] == 2
    assert counters["validated"] == 1


def test_concept_family_classification_is_not_a_rights_grant() -> None:
    assert canonical_classification(
        disposition=SourceDisposition.RIGHTS_REVIEW_REQUIRED,
        concept_is_new=True,
    ) == "canonical_candidate"
    assert canonical_classification(
        disposition=SourceDisposition.RIGHTS_REVIEW_REQUIRED,
        concept_is_new=False,
    ) == "legitimate_variant"
    assert canonical_classification(
        disposition=SourceDisposition.EXTERNAL_REFERENCE_ONLY,
        concept_is_new=True,
    ) == "reference_only"
    assert canonical_classification(
        disposition=SourceDisposition.REJECTED_PROPRIETARY,
        concept_is_new=True,
    ) == "rejected_quarantined"


def test_manifest_sha_mismatch_fails_closed(tmp_path: Path) -> None:
    source = tmp_path / "questions.jsonl"
    _write_jsonl(source, [_row("Q-001")])
    manifest = {
        "files": [
            {
                "file": source.name,
                "rows": 1,
                "sha256": hashlib.sha256(b"different bytes").hexdigest(),
            }
        ]
    }
    with pytest.raises(LargeCorpusError, match="SHA mismatch"):
        verify_physical_source(source, manifest=manifest)


def test_manifest_row_mismatch_fails_closed(tmp_path: Path) -> None:
    source = tmp_path / "questions.jsonl"
    _write_jsonl(source, [_row("Q-001")])
    manifest = {
        "files": [
            {
                "file": source.name,
                "rows": 2,
                "sha256": sha256_file(source),
            }
        ]
    }
    with pytest.raises(LargeCorpusError, match="row-count mismatch"):
        verify_physical_source(source, manifest=manifest)


def test_missing_physical_source_is_blocking(tmp_path: Path) -> None:
    with pytest.raises(LargeCorpusError, match="Physical corpus file not found"):
        verify_physical_source(tmp_path / "missing.parquet", manifest=None)
