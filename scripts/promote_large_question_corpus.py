#!/usr/bin/env python3
"""Quality-gated promotion from the 100K/1M reservoir into reviewable candidates.

Exact row/fingerprint uniqueness is necessary but not sufficient. Promotion is
bounded per reference-solution family and per conservative concept family so a
parameterized reservoir cannot inflate the candidate-facing catalog.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

from scripts.import_large_question_corpus import concept_identity, iter_rows, validate_row


def digest(value: object) -> str:
    return hashlib.sha256(str(value or "").strip().encode("utf-8")).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--batch-size", type=int, default=4096)
    parser.add_argument("--max-per-solution", type=int, default=25)
    parser.add_argument("--max-per-concept", type=int, default=10)
    parser.add_argument("--max-rows", type=int, default=100000)
    args = parser.parse_args()

    solution_counts: Counter[str] = Counter()
    concept_counts: Counter[str] = Counter()
    subjects: Counter[str] = Counter()
    reasons: Counter[str] = Counter()
    promoted = 0
    scanned = 0
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as stream:
        for _row_number, row in iter_rows(args.input, batch_size=args.batch_size):
            scanned += 1
            try:
                validate_row(row)
            except Exception:
                reasons["invalid_source_row"] += 1
                continue
            solution = str(row.get("solution") or "").strip()
            explanation = str(row.get("explanation") or "").strip()
            if len(solution) < 20:
                reasons["solution_too_short"] += 1
                continue
            if len(explanation) < 20:
                reasons["explanation_too_short"] += 1
                continue
            solution_key = digest(solution)
            concept_key = concept_identity(row)
            if solution_counts[solution_key] >= args.max_per_solution:
                reasons["solution_family_cap"] += 1
                continue
            if concept_counts[concept_key] >= args.max_per_concept:
                reasons["concept_family_cap"] += 1
                continue
            solution_counts[solution_key] += 1
            concept_counts[concept_key] += 1
            candidate: dict[str, Any] = dict(row)
            candidate["promotion_status"] = "awaiting_semantic_and_runtime_review"
            candidate["reservoir_source"] = str(args.input)
            stream.write(json.dumps(candidate, ensure_ascii=False, separators=(",", ":")) + "\n")
            promoted += 1
            subjects[str(row.get("subject") or "unknown")] += 1
            if promoted >= args.max_rows:
                reasons["promotion_limit_reached"] += 1
                break
    report = {
        "source": str(args.input),
        "scanned": scanned,
        "promoted": promoted,
        "unique_solution_families": len(solution_counts),
        "unique_concept_families": len(concept_counts),
        "max_per_solution": args.max_per_solution,
        "max_per_concept": args.max_per_concept,
        "by_subject": dict(sorted(subjects.items())),
        "gating_reasons": dict(sorted(reasons.items())),
        "policy": "Promotion creates review candidates only; it never auto-publishes or auto-enables execution.",
    }
    args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
