#!/usr/bin/env python3
"""Build the serving-ready attachment practice bank.

The input is the normalized, serving-deduplicated attachment JSONL.  Every output
record has a source-backed question, solution, and explanation.  If the dedicated
``explanation`` field is empty, the builder composes an explanation only from
other source-provided fields (expected approach, trade-offs, best practices,
common mistakes, and option analysis).  It never invents missing content.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any, Iterator


def read_jsonl(path: Path) -> Iterator[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, 1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(f"{path}:{line_number}: expected JSON object")
            yield value


def source_explanation(row: dict[str, Any]) -> tuple[str, str]:
    explicit = str(row.get("explanation") or "").strip()
    if explicit:
        return explicit, "explicit_explanation"

    pieces: list[str] = []
    for label, key in (
        ("Expected approach", "expected_approach"),
        ("Trade-offs", "tradeoffs"),
        ("Best practices", "best_practices"),
        ("Common mistakes", "common_mistakes"),
        ("Why other options are incorrect", "why_other_options_incorrect"),
    ):
        value = row.get(key)
        if isinstance(value, (dict, list)):
            value = json.dumps(value, ensure_ascii=False)
        text = str(value or "").strip()
        if text:
            pieces.append(f"{label}: {text}")
    return "\n\n".join(pieces), "source_fields_composed"


def build(source: Path, output_dir: Path) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    output = output_dir / "question_bank_with_solutions_explanations.jsonl"

    stats: Counter[str] = Counter()
    subjects: Counter[str] = Counter()
    tiers: Counter[str] = Counter()
    seen_ids: set[str] = set()

    with output.open("w", encoding="utf-8") as stream:
        for row in read_jsonl(source):
            canonical_id = str(row.get("canonical_id") or "").strip()
            question = str(row.get("question_statement") or "").strip()
            solution = str(row.get("solution") or "").strip()
            explanation, explanation_method = source_explanation(row)
            missing = [
                field
                for field, value in (
                    ("canonical_id", canonical_id),
                    ("question_statement", question),
                    ("solution", solution),
                    ("explanation", explanation),
                )
                if not value
            ]
            if missing:
                stats["rejected_missing_required"] += 1
                continue
            if canonical_id in seen_ids:
                stats["rejected_duplicate_id"] += 1
                continue
            seen_ids.add(canonical_id)

            row["explanation"] = explanation
            row["explanation_method"] = explanation_method
            row["runnable"] = False
            row["validation_status"] = "source_backed_content_validated"
            row["execution_validation_status"] = "pending_test_harness"
            row["solution_with_explanation"] = {
                "reference_solution": row.get("solution"),
                "explanation": explanation,
                "expected_approach": row.get("expected_approach"),
                "time_complexity": row.get("time_complexity"),
                "space_complexity": row.get("space_complexity"),
                "common_mistakes": row.get("common_mistakes"),
                "tradeoffs": row.get("tradeoffs"),
                "best_practices": row.get("best_practices"),
                "correct_answer": row.get("correct_answer"),
                "why_other_options_incorrect": row.get("why_other_options_incorrect"),
            }
            stream.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
            stats["emitted"] += 1
            stats[explanation_method] += 1
            subjects[str(row.get("subject") or "unknown")] += 1
            tiers[str(row.get("source_tier") or "unknown")] += 1

    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    manifest = {
        "dataset": "Rigor Attachment Question Bank",
        "version": "v1",
        "records": stats["emitted"],
        "source": str(source),
        "sha256": digest,
        "policy": {
            "source_backed_solutions_only": True,
            "explanations_must_be_source_backed": True,
            "source_fields_composed_explanation_allowed": True,
            "runnable_default": False,
            "execution_requires_public_hidden_tests": True,
        },
        "explanation_counts": {
            "explicit": stats["explicit_explanation"],
            "composed_from_source_fields": stats["source_fields_composed"],
            "rejected_missing_required": stats["rejected_missing_required"],
        },
        "duplicate_ids_rejected": stats["rejected_duplicate_id"],
        "subject_counts": dict(sorted(subjects.items())),
        "tier_counts": dict(sorted(tiers.items())),
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    manifest = build(args.input, args.output_dir)
    print(json.dumps(manifest, indent=2, ensure_ascii=False))
    if manifest["explanation_counts"]["rejected_missing_required"]:
        return 2
    if manifest["duplicate_ids_rejected"]:
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
