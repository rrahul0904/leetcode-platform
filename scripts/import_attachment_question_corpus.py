#!/usr/bin/env python3
"""Import the normalized attachment question corpus into Rigor hosted candidates.

The normalized bundle is produced from source attachments and must contain
`serving_feed_deduplicated.jsonl`.  This importer intentionally consumes the
serving feed rather than the raw 1M reservoir so candidate practice is not
inflated by repetitive parameterized variants.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import re
from typing import Any, Iterable


def slugify(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9]+", "-", value).strip("-")
    return value or "question"


def read_jsonl(path: pathlib.Path) -> Iterable[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as stream:
        for line_no, line in enumerate(stream, 1):
            if not line.strip():
                continue
            row = json.loads(line)
            if not row.get("canonical_id"):
                raise ValueError(f"{path}:{line_no}: canonical_id is required")
            if not row.get("question_statement"):
                raise ValueError(f"{path}:{line_no}: question_statement is required")
            if not row.get("solution"):
                raise ValueError(f"{path}:{line_no}: solution is required for serving feed")
            yield row


def topic_list(row: dict[str, Any]) -> list[str]:
    values = [row.get("subject"), row.get("topic"), row.get("subtopic"), row.get("platform")]
    out: list[str] = []
    for value in values:
        if not value:
            continue
        if isinstance(value, str):
            parts = re.split(r"[,/|]", value)
        else:
            parts = [str(value)]
        for part in parts:
            item = part.strip()
            if item and item not in out:
                out.append(item)
    return out


def to_hosted(row: dict[str, Any]) -> dict[str, Any]:
    canonical_id = str(row["canonical_id"])
    title = row.get("title") or row.get("subtopic") or row.get("topic") or canonical_id
    problem_markdown = row.get("question_markdown") or str(row["question_statement"])
    explanation = row.get("explanation") or ""
    solution = row.get("solution") or ""
    solution_language = row.get("solution_language")
    if not solution_language:
        platform = str(row.get("platform") or "").lower()
        if "python" in platform or "pyspark" in platform or "airflow" in platform:
            solution_language = "python"
        elif "sql" in platform or "snowflake" in platform or "bigquery" in platform:
            solution_language = "sql"
        else:
            solution_language = "text"

    return {
        "id": canonical_id,
        "slug": slugify(f"{canonical_id}-{title}"),
        "title": str(title),
        "difficulty": str(row.get("difficulty") or "unknown").lower(),
        "topics": topic_list(row),
        "companies": [],
        "company_frequency": {},
        "source_url": "",
        "problem_markdown": problem_markdown,
        "explanation_markdown": explanation,
        "reference_solution_language": solution_language,
        "reference_solution_code": solution,
        "correct_answer": row.get("correct_answer"),
        "options": row.get("options"),
        "status": "imported-draft",
        "runnable": False,
        "validation_notes": "Source-backed attachment corpus. Add/validate executable tests before enabling Run/Submit grading.",
        "source_package": row.get("source_package"),
        "source_bank": row.get("source_bank"),
        "source_question_id": row.get("source_question_id"),
        "source_tier": row.get("source_tier"),
        "source_question_file": row.get("source_question_file"),
        "source_solution_file": row.get("source_solution_file"),
        "serving_fingerprint_sha256": row.get("serving_fingerprint_sha256"),
    }


def build(input_dir: pathlib.Path, output: pathlib.Path) -> dict[str, Any]:
    source = input_dir / "serving_feed_deduplicated.jsonl"
    if not source.exists():
        raise FileNotFoundError(source)
    output.parent.mkdir(parents=True, exist_ok=True)

    count = 0
    tier_counts: dict[str, int] = {}
    subject_counts: dict[str, int] = {}
    with output.open("w", encoding="utf-8") as stream:
        for row in read_jsonl(source):
            hosted = to_hosted(row)
            stream.write(json.dumps(hosted, ensure_ascii=False, separators=(",", ":")) + "\n")
            count += 1
            tier = str(row.get("source_tier") or "unknown")
            tier_counts[tier] = tier_counts.get(tier, 0) + 1
            subject = str(row.get("subject") or "unknown")
            subject_counts[subject] = subject_counts.get(subject, 0) + 1

    manifest = {
        "input": str(source),
        "output": str(output),
        "hosted_candidates": count,
        "tier_counts": dict(sorted(tier_counts.items())),
        "subject_counts": dict(sorted(subject_counts.items())),
        "policy": "Consumes deduplicated solved serving feed; 1M reservoir is not promoted wholesale.",
    }
    output.with_suffix(".manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", type=pathlib.Path, required=True)
    parser.add_argument(
        "--output",
        type=pathlib.Path,
        default=pathlib.Path("data/question_upload/attachment_hosted_candidates.jsonl"),
    )
    args = parser.parse_args()
    print(json.dumps(build(args.input_dir, args.output), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
