#!/usr/bin/env python3
"""Synchronize the normalized attachment question bank into Rigor PostgreSQL.

This is the database-facing stage for the attachment corpus.  It consumes the
source-backed, serving-deduplicated JSONL produced by
``import_attachment_question_corpus.py`` / the attachment normalization job and
writes canonical questions, versions, solutions, provenance, and validation
records using the same tables as the governed content synchronizer.

Important policy:
- a row MUST contain a source-backed solution before it can be imported;
- executable grading is never inferred from the presence of solution code;
- imports are idempotent by external_id + version + content hash;
- publishing is explicit.  The default state is awaiting_technical_review.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable, Iterator
from uuid import UUID

from sqlalchemy import Connection, Engine, create_engine, text

VERSION = "attachment-v1"
SOURCE_AUTHOR_SUBJECT = "system:attachment-question-bank"
SOURCE_AUTHOR_EMAIL = "attachment-question-bank@rigor.test"
SOURCE_AUTHOR_NAME = "Attachment Question Bank Importer"

TRACK_CANDIDATES: dict[str, tuple[str, ...]] = {
    "python": ("python-engineering", "python", "software-engineering"),
    "python coding": ("python-engineering", "python", "software-engineering"),
    "sql": ("sql-analytics", "sql", "data-engineering"),
    "sql scenario": ("sql-analytics", "data-engineering", "sql"),
    "pyspark": ("data-engineering", "python-engineering", "pyspark"),
    "pyspark scenario": ("data-engineering", "pyspark", "python-engineering"),
    "data engineering": ("data-engineering", "sql-analytics"),
    "snowflake": ("data-engineering", "sql-analytics", "snowflake"),
    "databricks": ("data-engineering", "pyspark", "python-engineering"),
    "bigquery / gcp data": ("data-engineering", "sql-analytics"),
    "airflow / orchestration": ("data-engineering", "python-engineering"),
    "cloud engineering": ("data-engineering", "system-design"),
    "aws cloud": ("data-engineering", "system-design"),
    "azure cloud": ("data-engineering", "system-design"),
    "gcp cloud": ("data-engineering", "system-design"),
    "system design": ("system-design", "data-engineering"),
    "claude-style system design": ("system-design", "ai-engineering"),
    "codex-style system design": ("system-design", "ai-engineering"),
    "ai architecture": ("ai-engineering", "system-design", "data-engineering"),
    "ai / llm / agentic ai": ("ai-engineering", "system-design"),
    "data architecture / modeling": ("data-engineering", "system-design"),
    "governance / security / metadata / lineage": ("data-engineering", "system-design"),
}


@dataclass
class SyncReport:
    source: str
    version: str
    mode: str
    discovered: int = 0
    valid: int = 0
    invalid: int = 0
    inserted: int = 0
    updated: int = 0
    unchanged: int = 0
    published: int = 0
    skipped_unseeded_track: int = 0
    by_subject: dict[str, int] | None = None
    by_tier: dict[str, int] | None = None
    findings: list[dict[str, Any]] | None = None


def slugify(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9]+", "-", value).strip("-")
    return value or "question"


def read_jsonl(path: Path) -> Iterator[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as stream:
        for line_no, line in enumerate(stream, start=1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_no}: invalid JSON: {exc}") from exc
            row["_line_no"] = line_no
            yield row


def batches(rows: Iterable[dict[str, Any]], size: int) -> Iterator[list[dict[str, Any]]]:
    batch: list[dict[str, Any]] = []
    for row in rows:
        batch.append(row)
        if len(batch) >= size:
            yield batch
            batch = []
    if batch:
        yield batch


def normalize_difficulty(value: Any) -> str:
    difficulty = str(value or "medium").strip().lower()
    if difficulty in {"easy", "medium", "hard"}:
        return difficulty
    if difficulty in {"beginner", "basic"}:
        return "easy"
    if difficulty in {"advanced", "expert", "principal", "staff"}:
        return "hard"
    return "medium"


def expected_seniority(row: dict[str, Any]) -> str:
    value = str(row.get("seniority") or row.get("level") or "mid").strip().lower()
    if any(token in value for token in ("staff", "principal", "architect", "expert")):
        return "staff"
    if "senior" in value:
        return "senior"
    if any(token in value for token in ("junior", "entry", "associate", "beginner")):
        return "junior"
    return "mid"


def content_hash(row: dict[str, Any]) -> str:
    stable = {key: value for key, value in row.items() if not key.startswith("_")}
    encoded = json.dumps(stable, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def validate_row(row: dict[str, Any]) -> list[str]:
    findings: list[str] = []
    for field in ("canonical_id", "question_statement", "solution"):
        if not str(row.get(field) or "").strip():
            findings.append(f"missing required field: {field}")
    if not str(row.get("explanation") or "").strip():
        findings.append("missing explanation")
    if row.get("runnable") is True:
        findings.append(
            "attachment import cannot declare runnable=true without governed public/hidden tests"
        )
    return findings


def resolve_track(connection: Connection, row: dict[str, Any]) -> tuple[UUID | None, str | None]:
    subject = str(row.get("subject") or "").strip().casefold()
    platform = str(row.get("platform") or "").strip().casefold()
    candidates = list(TRACK_CANDIDATES.get(subject, ()))
    candidates.extend(TRACK_CANDIDATES.get(platform, ()))
    if not candidates:
        if "sql" in subject or "sql" in platform:
            candidates.extend(("sql-analytics", "data-engineering"))
        elif "python" in subject or "python" in platform:
            candidates.extend(("python-engineering", "data-engineering"))
        elif "system" in subject and "design" in subject:
            candidates.extend(("system-design", "data-engineering"))
        elif "ai" in subject or "llm" in subject:
            candidates.extend(("ai-engineering", "system-design"))
        else:
            candidates.extend(("data-engineering", "system-design"))
    candidates = list(dict.fromkeys(candidates))
    result = connection.execute(
        text("SELECT id, slug FROM question_tracks WHERE slug = ANY(:slugs)"),
        {"slugs": candidates},
    ).mappings()
    found = {str(item["slug"]): item["id"] for item in result}
    for slug in candidates:
        if slug in found:
            return UUID(str(found[slug])), slug
    return None, None


def ensure_import_actor(connection: Connection) -> UUID:
    return UUID(
        str(
            connection.execute(
                text(
                    """
                    INSERT INTO users (identity_subject, email, display_name, email_verified)
                    VALUES (:subject, :email, :display_name, true)
                    ON CONFLICT (identity_subject) DO UPDATE SET
                        display_name=EXCLUDED.display_name,
                        email=EXCLUDED.email,
                        updated_at=CURRENT_TIMESTAMP
                    RETURNING id
                    """
                ),
                {
                    "subject": SOURCE_AUTHOR_SUBJECT,
                    "email": SOURCE_AUTHOR_EMAIL,
                    "display_name": SOURCE_AUTHOR_NAME,
                },
            ).scalar_one()
        )
    )


def question_structured_content(row: dict[str, Any], track_slug: str) -> dict[str, Any]:
    return {
        "attachment_schema_version": 1,
        "canonical_id": row.get("canonical_id"),
        "source_package": row.get("source_package"),
        "source_bank": row.get("source_bank"),
        "source_question_id": row.get("source_question_id"),
        "source_tier": row.get("source_tier"),
        "subject": row.get("subject"),
        "platform": row.get("platform"),
        "topic": row.get("topic"),
        "subtopic": row.get("subtopic"),
        "question_type": row.get("question_type"),
        "business_context": row.get("business_context"),
        "input_output_or_schema": row.get("input_output_or_schema"),
        "requirements": row.get("requirements"),
        "constraints": row.get("constraints"),
        "expected_approach": row.get("expected_approach"),
        "explanation": row.get("explanation"),
        "time_complexity": row.get("time_complexity"),
        "space_complexity": row.get("space_complexity"),
        "common_mistakes": row.get("common_mistakes"),
        "options": row.get("options"),
        "correct_answer": row.get("correct_answer"),
        "why_other_options_incorrect": row.get("why_other_options_incorrect"),
        "tradeoffs": row.get("tradeoffs"),
        "best_practices": row.get("best_practices"),
        "tags": row.get("tags"),
        "solution_language": row.get("solution_language"),
        "runnable": False,
        "primary_track": track_slug,
        "serving_fingerprint_sha256": row.get("serving_fingerprint_sha256"),
        "source_question_file": row.get("source_question_file"),
        "source_solution_file": row.get("source_solution_file"),
    }


def upsert_one(
    connection: Connection,
    row: dict[str, Any],
    *,
    source_revision: str,
    publish: bool,
) -> tuple[str, bool]:
    track_id, track_slug = resolve_track(connection, row)
    if track_id is None or track_slug is None:
        return "unseeded_track", False

    canonical_id = str(row["canonical_id"])
    title = str(row.get("title") or row.get("subtopic") or row.get("topic") or canonical_id)
    digest = content_hash(row)
    slug = slugify(f"{canonical_id}-{title}")[:250]

    question_id = UUID(
        str(
            connection.execute(
                text(
                    """
                    INSERT INTO questions (external_id, slug, primary_track_id)
                    VALUES (:external_id, :slug, :track_id)
                    ON CONFLICT (external_id) DO UPDATE SET
                        slug=EXCLUDED.slug,
                        primary_track_id=EXCLUDED.primary_track_id,
                        updated_at=CURRENT_TIMESTAMP
                    RETURNING id
                    """
                ),
                {"external_id": canonical_id, "slug": slug, "track_id": track_id},
            ).scalar_one()
        )
    )

    existing = (
        connection.execute(
            text(
                """
                SELECT id, content_hash, state::text AS state
                FROM question_versions
                WHERE question_id=:question_id AND version=:version
                """
            ),
            {"question_id": question_id, "version": VERSION},
        )
        .mappings()
        .one_or_none()
    )
    if existing and existing["content_hash"] == digest:
        if publish and existing["state"] != "published":
            connection.execute(
                text(
                    "UPDATE question_versions SET state='published'::content_state, "
                    "updated_at=CURRENT_TIMESTAMP WHERE id=:id"
                ),
                {"id": existing["id"]},
            )
            connection.execute(
                text(
                    "UPDATE questions SET current_published_version_id=:version_id, "
                    "archived_at=NULL, updated_at=CURRENT_TIMESTAMP WHERE id=:question_id"
                ),
                {"version_id": existing["id"], "question_id": question_id},
            )
            return "unchanged", True
        return "unchanged", existing["state"] == "published"

    structured = question_structured_content(row, track_slug)
    difficulty = normalize_difficulty(row.get("difficulty"))
    values = {
        "question_id": question_id,
        "version": VERSION,
        "title": title,
        "problem_statement": str(row["question_statement"]),
        "expected_seniority": expected_seniority(row),
        "difficulty": difficulty,
        "conceptual": 2 if difficulty == "easy" else 3 if difficulty == "medium" else 4,
        "implementation": 2 if difficulty == "easy" else 3 if difficulty == "medium" else 4,
        "scale": 2 if difficulty == "easy" else 3 if difficulty == "medium" else 4,
        "ambiguity": 2 if difficulty == "easy" else 3 if difficulty == "medium" else 4,
        "prerequisite_depth": 2 if difficulty == "easy" else 3 if difficulty == "medium" else 4,
        "duration": 30 if difficulty == "easy" else 45 if difficulty == "medium" else 60,
        "state": "published" if publish else "awaiting_technical_review",
        "structured": json.dumps(structured, ensure_ascii=False),
        "content_hash": digest,
        "source_revision": source_revision[:64],
    }

    if existing:
        if existing["state"] in {"approved", "published"}:
            # Published/approved versions are immutable. Preserve the old version and let a
            # source revision bump create a future attachment-v2 migration instead.
            return "immutable_existing", existing["state"] == "published"
        values["version_id"] = existing["id"]
        connection.execute(
            text(
                """
                UPDATE question_versions SET
                    title=:title,
                    problem_statement=:problem_statement,
                    expected_seniority=:expected_seniority,
                    difficulty=:difficulty,
                    conceptual_difficulty=:conceptual,
                    implementation_difficulty=:implementation,
                    scale=:scale,
                    ambiguity=:ambiguity,
                    prerequisite_depth=:prerequisite_depth,
                    duration_minutes=:duration,
                    state=CAST(:state AS content_state),
                    structured_content=CAST(:structured AS jsonb),
                    content_hash=:content_hash,
                    source_revision=:source_revision,
                    updated_at=CURRENT_TIMESTAMP
                WHERE id=:version_id
                """
            ),
            values,
        )
        version_id = UUID(str(existing["id"]))
        action = "updated"
    else:
        version_id = UUID(
            str(
                connection.execute(
                    text(
                        """
                        INSERT INTO question_versions (
                            question_id, version, title, problem_statement,
                            expected_seniority, difficulty, conceptual_difficulty,
                            implementation_difficulty, scale, ambiguity, prerequisite_depth,
                            duration_minutes, state, structured_content, content_hash,
                            source_revision
                        ) VALUES (
                            :question_id, :version, :title, :problem_statement,
                            :expected_seniority, :difficulty, :conceptual, :implementation,
                            :scale, :ambiguity, :prerequisite_depth, :duration,
                            CAST(:state AS content_state), CAST(:structured AS jsonb),
                            :content_hash, :source_revision
                        ) RETURNING id
                        """
                    ),
                    values,
                ).scalar_one()
            )
        )
        action = "inserted"

    # Replace only attachment-owned sidecars.  This keeps the operation idempotent and
    # prevents solution/explanation duplication across retries.
    connection.execute(
        text("DELETE FROM solutions WHERE question_version_id=:version_id"),
        {"version_id": version_id},
    )
    connection.execute(
        text(
            """
            INSERT INTO solutions (
                question_version_id, reference_solution, explanation,
                trade_off_analysis, source_content_hash
            ) VALUES (
                :version_id, :reference_solution, :explanation,
                CAST(:trade_offs AS jsonb), :source_hash
            )
            """
        ),
        {
            "version_id": version_id,
            "reference_solution": str(row["solution"]),
            "explanation": str(row.get("explanation") or ""),
            "trade_offs": json.dumps(
                {
                    "tradeoffs": row.get("tradeoffs"),
                    "best_practices": row.get("best_practices"),
                    "time_complexity": row.get("time_complexity"),
                    "space_complexity": row.get("space_complexity"),
                    "common_mistakes": row.get("common_mistakes"),
                    "expected_approach": row.get("expected_approach"),
                },
                ensure_ascii=False,
            ),
            "source_hash": digest,
        },
    )

    actor_id = ensure_import_actor(connection)
    connection.execute(
        text("DELETE FROM provenance_records WHERE question_version_id=:version_id"),
        {"version_id": version_id},
    )
    connection.execute(
        text(
            """
            INSERT INTO provenance_records (
                question_version_id, author_id, originality_statement,
                authoring_method, source_notes
            ) VALUES (
                :version_id, :author_id, :originality, :method,
                CAST(:source_notes AS jsonb)
            )
            """
        ),
        {
            "version_id": version_id,
            "author_id": actor_id,
            "originality": "Imported from user-provided source-backed attachment corpus.",
            "method": "attachment-corpus-import",
            "source_notes": json.dumps(
                {
                    "source_package": row.get("source_package"),
                    "source_bank": row.get("source_bank"),
                    "source_question_id": row.get("source_question_id"),
                    "source_tier": row.get("source_tier"),
                    "source_question_file": row.get("source_question_file"),
                    "source_solution_file": row.get("source_solution_file"),
                    "serving_fingerprint_sha256": row.get("serving_fingerprint_sha256"),
                },
                ensure_ascii=False,
            ),
        },
    )

    connection.execute(
        text(
            """
            INSERT INTO validation_runs (
                question_version_id, validator_version, status, findings,
                started_at, completed_at
            ) VALUES (
                :version_id, 'attachment-source-validation-v1', 'passed',
                CAST(:findings AS jsonb), CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            )
            """
        ),
        {
            "version_id": version_id,
            "findings": json.dumps(
                [
                    "source-backed question present",
                    "source-backed solution present",
                    "source-backed explanation present",
                    "serving fingerprint deduplicated before import",
                    "executable grading not enabled until public/hidden tests validate",
                ]
            ),
        },
    )

    if publish:
        current = connection.execute(
            text("SELECT current_published_version_id FROM questions WHERE id=:question_id"),
            {"question_id": question_id},
        ).scalar_one_or_none()
        if current and str(current) != str(version_id):
            connection.execute(
                text(
                    "UPDATE question_versions SET state='deprecated'::content_state, "
                    "updated_at=CURRENT_TIMESTAMP WHERE id=:id"
                ),
                {"id": current},
            )
        connection.execute(
            text(
                "UPDATE questions SET current_published_version_id=:version_id, "
                "archived_at=NULL, updated_at=CURRENT_TIMESTAMP WHERE id=:question_id"
            ),
            {"version_id": version_id, "question_id": question_id},
        )

    connection.execute(
        text(
            """
            INSERT INTO audit_events (
                actor_user_id, action, resource_type, resource_id,
                details, correlation_id
            ) VALUES (
                :actor_id, 'content.attachment_imported', 'question_version', :resource_id,
                CAST(:details AS jsonb), 'attachment-question-bank'
            )
            """
        ),
        {
            "actor_id": actor_id,
            "resource_id": str(version_id),
            "details": json.dumps(
                {
                    "canonical_id": canonical_id,
                    "source_revision": source_revision,
                    "source_tier": row.get("source_tier"),
                    "published": publish,
                    "runnable": False,
                }
            ),
        },
    )
    return action, publish


def build_engine(database_url: str) -> Engine:
    return create_engine(database_url, pool_pre_ping=True, pool_size=5, max_overflow=5)


def run(args: argparse.Namespace) -> SyncReport:
    rows = list(read_jsonl(args.input))
    subject_counts = Counter(str(row.get("subject") or "unknown") for row in rows)
    tier_counts = Counter(str(row.get("source_tier") or "unknown") for row in rows)
    report = SyncReport(
        source=str(args.input),
        version=VERSION,
        mode=args.mode,
        discovered=len(rows),
        by_subject=dict(sorted(subject_counts.items())),
        by_tier=dict(sorted(tier_counts.items())),
        findings=[],
    )

    valid_rows: list[dict[str, Any]] = []
    for row in rows:
        findings = validate_row(row)
        if findings:
            report.invalid += 1
            if len(report.findings or []) < args.max_findings:
                report.findings.append(
                    {
                        "line": row.get("_line_no"),
                        "canonical_id": row.get("canonical_id"),
                        "findings": findings,
                    }
                )
            continue
        report.valid += 1
        valid_rows.append(row)

    if args.mode == "validate":
        return report

    database_url = args.database_url or os.getenv("DATABASE_URL")
    if not database_url:
        raise SystemExit("DATABASE_URL or --database-url is required for dry-run/sync")
    engine = build_engine(database_url)

    if args.mode == "dry-run":
        with engine.connect() as connection:
            seeded = {
                str(row[0])
                for row in connection.execute(text("SELECT slug FROM question_tracks ORDER BY slug"))
            }
            missing: set[str] = set()
            for row in valid_rows:
                candidates = TRACK_CANDIDATES.get(
                    str(row.get("subject") or "").strip().casefold(),
                    ("data-engineering", "system-design"),
                )
                if not any(candidate in seeded for candidate in candidates):
                    missing.add(str(row.get("subject") or "unknown"))
            if missing:
                report.findings.append({"unseeded_subjects": sorted(missing)})
        return report

    for batch in batches(valid_rows, args.batch_size):
        with engine.begin() as connection:
            for row in batch:
                publish = args.publish_all or str(row.get("source_tier") or "") in args.publish_tier
                action, was_published = upsert_one(
                    connection,
                    row,
                    source_revision=args.source_revision,
                    publish=publish,
                )
                if action == "inserted":
                    report.inserted += 1
                elif action == "updated":
                    report.updated += 1
                elif action == "unchanged":
                    report.unchanged += 1
                elif action == "unseeded_track":
                    report.skipped_unseeded_track += 1
                elif action == "immutable_existing":
                    report.unchanged += 1
                if was_published:
                    report.published += 1

    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--input",
        type=Path,
        required=True,
        help="serving_feed_deduplicated.jsonl or an equivalent source-backed JSONL",
    )
    parser.add_argument("--database-url")
    parser.add_argument(
        "--mode",
        choices=("validate", "dry-run", "sync"),
        default="validate",
    )
    parser.add_argument("--batch-size", type=int, default=250)
    parser.add_argument("--max-findings", type=int, default=100)
    parser.add_argument("--source-revision", default="attachment-question-bank-v1")
    parser.add_argument(
        "--publish-tier",
        action="append",
        default=[],
        help=(
            "Explicitly publish a source tier after import, e.g. "
            "--publish-tier A_curated_explained. May be repeated."
        ),
    )
    parser.add_argument(
        "--publish-all",
        action="store_true",
        help="Publish all source-backed imported rows. Does not make coding rows runnable.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = run(args)
    print(json.dumps(asdict(report), indent=2, ensure_ascii=False))
    if report.invalid:
        return 2
    if report.skipped_unseeded_track:
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
