#!/usr/bin/env python3
"""Assess source-backed candidates against Rigor's runnable publication contract."""

from __future__ import annotations

import argparse
import base64
import io
import json
import zipfile
from collections import Counter
from pathlib import Path
from typing import TypedDict, cast

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ARCHIVE = (
    ROOT / "content" / "imported" / "source-backed" / "question-bank.zip.b64"
)
DEFAULT_LIMIT = 25
SUPPORTED_RUNTIMES = {"py": "python", "python": "python"}


class JsonObject(TypedDict, total=False):
    slug: object
    title: object
    problem_markdown: object
    explanation_markdown: object
    reference_solution_language: object
    reference_solution_code: object
    companies: object
    topics: object
    rights_disposition: object
    starter_code: object
    public_tests: object
    hidden_tests: object
    reference_tests_passed: object
    editorial_markdown: object
    publication_approved: object


class CandidateAssessment(TypedDict):
    slug: str
    title: str
    language: str | None
    availability: str
    priority_score: int
    blockers: list[str]
    company_count: int
    topic_count: int


def _text(value: object) -> str:
    return str(value or "").strip()


def _object_list(value: object) -> list[object]:
    return cast(list[object], value) if isinstance(value, list) else []


def _jsonl(bundle: zipfile.ZipFile, name: str) -> list[JsonObject]:
    rows: list[JsonObject] = []
    with bundle.open(name) as stream:
        for line_number, raw in enumerate(stream, 1):
            if not raw.strip():
                continue
            value: object = json.loads(raw)
            if not isinstance(value, dict):
                raise ValueError(f"{name}:{line_number} must be a JSON object")
            rows.append(cast(JsonObject, value))
    return rows


def load_candidates(archive_path: Path) -> list[JsonObject]:
    encoded = "".join(archive_path.read_text(encoding="ascii").split())
    archive_bytes = base64.b64decode(encoded, validate=True)
    with zipfile.ZipFile(io.BytesIO(archive_bytes)) as bundle:
        return _jsonl(bundle, "hosted_question_candidates.jsonl")


def assess_candidate(row: JsonObject) -> CandidateAssessment:
    statement = _text(row.get("problem_markdown"))
    solution = _text(row.get("reference_solution_code"))
    explanation = _text(
        row.get("editorial_markdown") or row.get("explanation_markdown")
    )
    source_language = _text(row.get("reference_solution_language")).casefold()
    runtime = SUPPORTED_RUNTIMES.get(source_language)
    companies = _object_list(row.get("companies"))
    topics = _object_list(row.get("topics"))
    public_tests = _object_list(row.get("public_tests"))
    hidden_tests = _object_list(row.get("hidden_tests"))

    blockers: list[str] = []
    if len(statement) < 200:
        blockers.append("statement_missing_or_too_short")
    if not solution:
        blockers.append("reference_solution_missing")
    if runtime is None:
        blockers.append("runtime_unsupported")
    if _text(row.get("rights_disposition")).casefold() != "hostable_licensed":
        blockers.append("rights_not_approved")
    if not _text(row.get("starter_code")):
        blockers.append("starter_code_missing")
    if not public_tests:
        blockers.append("public_tests_missing")
    if not hidden_tests:
        blockers.append("hidden_tests_missing")
    if row.get("reference_tests_passed") is not True:
        blockers.append("reference_validation_missing")
    if not explanation:
        blockers.append("editorial_missing")
    if row.get("publication_approved") is not True:
        blockers.append("publication_approval_missing")

    if not statement:
        availability = "reference_only"
    elif blockers:
        availability = "in_review"
    else:
        availability = "runnable"

    priority_score = (
        (40 if len(statement) >= 200 else 0)
        + (30 if solution else 0)
        + (10 if runtime == "python" else 0)
        + (10 if explanation else 0)
        + min(len(companies), 5)
        + min(len(topics), 5)
    )
    return {
        "slug": _text(row.get("slug")),
        "title": _text(row.get("title")),
        "language": runtime,
        "availability": availability,
        "priority_score": priority_score,
        "blockers": blockers,
        "company_count": len(companies),
        "topic_count": len(topics),
    }


def build_report(
    candidates: list[JsonObject],
    *,
    review_limit: int = DEFAULT_LIMIT,
) -> dict[str, object]:
    assessments = [assess_candidate(candidate) for candidate in candidates]
    assessments.sort(key=lambda item: (-item["priority_score"], item["slug"]))
    availability_counts = Counter(
        assessment["availability"] for assessment in assessments
    )
    blocker_counts = Counter(
        blocker
        for assessment in assessments
        for blocker in assessment["blockers"]
    )
    return {
        "summary": {
            "total_candidates": len(assessments),
            "runnable": availability_counts["runnable"],
            "in_review": availability_counts["in_review"],
            "reference_only": availability_counts["reference_only"],
            "review_queue_size": min(review_limit, len(assessments)),
        },
        "blocker_counts": dict(sorted(blocker_counts.items())),
        "review_queue": assessments[:review_limit],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--archive", type=Path, default=DEFAULT_ARCHIVE)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT)
    args = parser.parse_args()
    if args.limit <= 0:
        parser.error("--limit must be greater than zero")

    report = build_report(load_candidates(args.archive), review_limit=args.limit)
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
