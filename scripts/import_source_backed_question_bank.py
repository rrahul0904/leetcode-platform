#!/usr/bin/env python3
"""Import the generated source-backed bank into Rigor's native knowledge tables."""

from __future__ import annotations

import argparse
import base64
import hashlib
import io
import json
import os
import re
import zipfile
from pathlib import Path
from typing import cast

from rigor_api.config import get_settings
from rigor_api.database import create_database_engine
from rigor_api.knowledge_store import import_knowledge_payload

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ARCHIVE = (
    ROOT / "content" / "imported" / "source-backed" / "question-bank.zip.b64"
)
JsonObject = dict[str, object]
EXPECTED_IMPORT_COUNTS = {
    "problems": 3425,
    "solutions": 120,
    "company_observations": 35348,
    "system_design_articles": 29,
}


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


def _object_list(value: object) -> list[object]:
    return cast(list[object], value) if isinstance(value, list) else []


def _object_dict(value: object) -> JsonObject:
    return cast(JsonObject, value) if isinstance(value, dict) else {}


def _last_object(value: object) -> JsonObject:
    values = _object_list(value)
    return _object_dict(values[-1]) if values else {}


def _hash(value: object) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _difficulty(value: object) -> str | None:
    normalized = str(value or "").strip().casefold()
    aliases = {
        "easy": "easy",
        "medium": "medium",
        "hard": "hard",
        "foundational": "easy",
        "intermediate": "medium",
        "advanced": "hard",
    }
    return aliases.get(normalized)


def _language(value: object) -> str | None:
    normalized = str(value or "").strip().casefold()
    aliases = {
        "py": "python",
        "python": "python",
        "js": "javascript",
        "javascript": "javascript",
        "sql": "sql",
        "cpp": "cpp",
        "c++": "cpp",
        "java": "java",
        "go": "go",
        "c": "c",
        "kt": "kotlin",
        "cs": "csharp",
        "dart": "dart",
    }
    return aliases.get(normalized)


def _frequency(value: object) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value or "").strip().replace("%", "")
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _headings(markdown: str) -> list[str]:
    return [
        match.group(1).strip()
        for match in re.finditer(r"^#{1,6}\s+(.+?)\s*$", markdown, re.MULTILINE)
        if match.group(1).strip()
    ]


def _solution_record(
    hosted_row: JsonObject,
    *,
    canonical_key: str,
    slug: str,
) -> JsonObject | None:
    language = _language(hosted_row.get("reference_solution_language"))
    code = str(hosted_row.get("reference_solution_code") or "")
    if not language or not code.strip():
        return None
    solution_source = _last_object(hosted_row.get("source_files"))
    return {
        "canonical_key": canonical_key,
        "language": language,
        "source_code": code,
        "explanation": str(hosted_row.get("explanation_markdown") or "") or None,
        "source_name": str(
            solution_source.get("archive")
            or "uploaded-source-backed-question-bank"
        ),
        "source_path": str(
            solution_source.get("path")
            or f"hosted_question_candidates.jsonl#{slug}"
        ),
        "source_hash": hashlib.sha256(code.encode("utf-8")).hexdigest(),
        "disposition": "rights_review_required",
    }


def load_payload(archive_path: Path) -> dict[str, object]:
    encoded = "".join(archive_path.read_text(encoding="ascii").split())
    archive_bytes = base64.b64decode(encoded, validate=True)
    with zipfile.ZipFile(io.BytesIO(archive_bytes)) as bundle:
        external = _jsonl(bundle, "external_question_index.jsonl")
        hosted = _jsonl(bundle, "hosted_question_candidates.jsonl")
        system_design = _jsonl(bundle, "system_design_resources.jsonl")
        manifest_value: object = json.loads(bundle.read("manifest.json"))
    if not isinstance(manifest_value, dict):
        raise ValueError("manifest.json must contain a JSON object")
    manifest = cast(JsonObject, manifest_value)

    hosted_by_slug = {str(row["slug"]): row for row in hosted}
    problems: list[JsonObject] = []
    solutions: list[JsonObject] = []
    companies: list[JsonObject] = []

    for row in external:
        slug = str(row["slug"])
        hosted_row = hosted_by_slug.get(slug)
        links = _object_list(row.get("links"))
        source_url = (
            str(hosted_row.get("source_url"))
            if hosted_row and hosted_row.get("source_url")
            else (
                str(links[0])
                if links
                else f"https://leetcode.com/problems/{slug}/"
            )
        )
        description = (
            str(hosted_row.get("problem_markdown") or "")
            if hosted_row
            else None
        )
        canonical_key = f"leetcode:{slug}"
        problem_record: JsonObject = {
            "canonical_key": canonical_key,
            "external_id": slug,
            "title": str(row.get("title") or slug.replace("-", " ").title()),
            "slug": f"leetcode-{slug}",
            "description": description,
            "difficulty": _difficulty(row.get("difficulty")),
            "source_url": source_url,
            "topics": _object_list(row.get("topics")),
            "source_name": "uploaded-source-backed-question-bank",
            "source_path": f"external_question_index.jsonl#{slug}",
            "source_hash": _hash(row),
            "disposition": "external_reference_only",
        }
        problems.append(problem_record)

        frequency_map = _object_dict(row.get("company_frequency"))
        company_names = _object_list(row.get("companies"))
        for company_value in company_names:
            company = str(company_value)
            windows = _object_dict(frequency_map.get(company))
            if not windows:
                windows = {"unknown": None}
            numeric_frequencies = [
                value
                for value in (_frequency(raw) for raw in windows.values())
                if value is not None
            ]
            aggregated_frequency = (
                max(numeric_frequencies) if numeric_frequencies else None
            )
            observation: JsonObject = {
                "canonical_key": canonical_key,
                "external_id": slug,
                "title": problem_record["title"],
                "difficulty": problem_record["difficulty"],
                "problem_url": source_url,
                "topics": problem_record["topics"],
                "company": company,
                "observation_window": "aggregated",
                "frequency": aggregated_frequency,
                "source_name": "uploaded-source-backed-question-bank",
                "source_path": f"company/{company}/aggregated.csv",
                "source_hash": _hash(
                    {
                        "slug": slug,
                        "company": company,
                        "windows": windows,
                    }
                ),
            }
            companies.append(observation)

        if hosted_row:
            solution = _solution_record(
                hosted_row,
                canonical_key=canonical_key,
                slug=slug,
            )
            if solution:
                solutions.append(solution)

    imported_slugs = {str(row["slug"]) for row in external}
    for hosted_row in hosted:
        slug = str(hosted_row["slug"])
        if slug in imported_slugs:
            continue
        canonical_key = f"leetcode:{slug}"
        problems.append(
            {
                "canonical_key": canonical_key,
                "external_id": slug,
                "title": str(
                    hosted_row.get("title") or slug.replace("-", " ").title()
                ),
                "slug": f"leetcode-{slug}",
                "description": str(hosted_row.get("problem_markdown") or "") or None,
                "difficulty": _difficulty(hosted_row.get("difficulty")),
                "source_url": str(
                    hosted_row.get("source_url")
                    or f"https://leetcode.com/problems/{slug}/"
                ),
                "topics": _object_list(hosted_row.get("topics")),
                "source_name": "uploaded-source-backed-question-bank",
                "source_path": f"hosted_question_candidates.jsonl#{slug}",
                "source_hash": _hash(hosted_row),
                "disposition": "external_reference_only",
            }
        )
        solution = _solution_record(
            hosted_row,
            canonical_key=canonical_key,
            slug=slug,
        )
        if solution:
            solutions.append(solution)

    articles: list[JsonObject] = []
    for row in system_design:
        body = str(row.get("markdown") or "")
        if not body.strip():
            continue
        row_slug = str(row["slug"])
        articles.append(
            {
                "slug": f"uploaded-{row_slug}",
                "title": str(row.get("title") or row_slug),
                "body": body,
                "headings": _headings(body),
                "image_paths": [],
                "source_name": str(
                    row.get("source_archive") or "uploaded-system-design-notes"
                ),
                "source_path": str(
                    row.get("source_path")
                    or f"system_design_resources.jsonl#{row_slug}"
                ),
                "source_hash": hashlib.sha256(body.encode("utf-8")).hexdigest(),
                "disposition": "external_reference_only",
            }
        )

    return {
        "source_name": "uploaded-source-backed-question-bank",
        "disposition": "external_reference_only",
        "manifest": manifest,
        "files": [],
        "problems": problems,
        "solutions": solutions,
        "companies": companies,
        "system_design": articles,
        "resources": [],
    }


def validate_payload(payload: dict[str, object]) -> dict[str, int]:
    problems = payload["problems"]
    solutions = payload["solutions"]
    companies = payload["companies"]
    system_design = payload["system_design"]
    assert isinstance(problems, list)
    assert isinstance(solutions, list)
    assert isinstance(companies, list)
    assert isinstance(system_design, list)
    counts = {
        "problems": len(problems),
        "solutions": len(solutions),
        "company_observations": len(companies),
        "system_design_articles": len(system_design),
    }
    for key, expected in EXPECTED_IMPORT_COUNTS.items():
        actual = counts[key]
        if actual != expected:
            raise ValueError(f"expected {expected} {key.replace('_', ' ')}, found {actual}")
    return counts


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--archive", type=Path, default=DEFAULT_ARCHIVE)
    parser.add_argument("--database-url", default=os.getenv("RIGOR_DATABASE_URL"))
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    payload = load_payload(args.archive)
    counts = validate_payload(payload)
    if args.validate_only:
        print(json.dumps({"status": "valid", **counts}, indent=2, sort_keys=True))
        return 0

    settings = get_settings()
    database_url = (
        args.database_url
        or settings.operational_database_url
        or settings.database_url
    )
    engine = create_database_engine(settings, database_url)
    try:
        result = import_knowledge_payload(engine, payload, dry_run=args.dry_run)
    finally:
        engine.dispose()
    print(
        json.dumps(
            {"source_bank": counts, "database_import": result},
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
