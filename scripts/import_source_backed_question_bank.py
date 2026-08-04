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
from typing import Any

from rigor_api.config import get_settings
from rigor_api.database import create_database_engine
from rigor_api.knowledge_store import import_knowledge_payload

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ARCHIVE = ROOT / "content" / "imported" / "source-backed" / "question-bank.zip.b64"


def _jsonl(bundle: zipfile.ZipFile, name: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with bundle.open(name) as stream:
        for line_number, raw in enumerate(stream, 1):
            if not raw.strip():
                continue
            value = json.loads(raw)
            if not isinstance(value, dict):
                raise ValueError(f"{name}:{line_number} must be a JSON object")
            rows.append(value)
    return rows


def _hash(value: object) -> str:
    encoded = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
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


def load_payload(archive_path: Path) -> dict[str, object]:
    encoded = "".join(archive_path.read_text(encoding="ascii").split())
    archive_bytes = base64.b64decode(encoded, validate=True)
    with zipfile.ZipFile(io.BytesIO(archive_bytes)) as bundle:
        external = _jsonl(bundle, "external_question_index.jsonl")
        hosted = _jsonl(bundle, "hosted_question_candidates.jsonl")
        system_design = _jsonl(bundle, "system_design_resources.jsonl")
        manifest = json.loads(bundle.read("manifest.json"))

    hosted_by_slug = {str(row["slug"]): row for row in hosted}
    problems: list[dict[str, object]] = []
    solutions: list[dict[str, object]] = []
    companies: list[dict[str, object]] = []

    for row in external:
        slug = str(row["slug"])
        hosted_row = hosted_by_slug.get(slug)
        links = row.get("links") if isinstance(row.get("links"), list) else []
        source_url = (
            str(hosted_row.get("source_url"))
            if hosted_row and hosted_row.get("source_url")
            else (str(links[0]) if links else f"https://leetcode.com/problems/{slug}/")
        )
        description = (
            str(hosted_row.get("problem_markdown") or "")
            if hosted_row
            else None
        )
        canonical_key = f"leetcode:{slug}"
        problem_record = {
            "canonical_key": canonical_key,
            "external_id": slug,
            "title": str(row.get("title") or slug.replace("-", " ").title()),
            "slug": f"leetcode-{slug}",
            "description": description,
            "difficulty": _difficulty(row.get("difficulty")),
            "source_url": source_url,
            "topics": row.get("topics") if isinstance(row.get("topics"), list) else [],
            "source_name": "uploaded-source-backed-question-bank",
            "source_path": f"external_question_index.jsonl#{slug}",
            "source_hash": _hash(row),
            "disposition": "external_reference_only",
        }
        problems.append(problem_record)

        frequency_map = (
            row.get("company_frequency")
            if isinstance(row.get("company_frequency"), dict)
            else {}
        )
        company_names = row.get("companies") if isinstance(row.get("companies"), list) else []
        for company in company_names:
            windows = frequency_map.get(company)
            if not isinstance(windows, dict) or not windows:
                windows = {"unknown": None}
            numeric_frequencies = [
                value
                for value in (_frequency(raw) for raw in windows.values())
                if value is not None
            ]
            aggregated_frequency = (
                max(numeric_frequencies) if numeric_frequencies else None
            )
            observation = {
                "canonical_key": canonical_key,
                "external_id": slug,
                "title": problem_record["title"],
                "difficulty": problem_record["difficulty"],
                "problem_url": source_url,
                "topics": problem_record["topics"],
                "company": str(company),
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
            language = _language(hosted_row.get("reference_solution_language"))
            code = str(hosted_row.get("reference_solution_code") or "")
            if language and code.strip():
                source_files = hosted_row.get("source_files")
                solution_source = (
                    source_files[-1]
                    if isinstance(source_files, list)
                    and source_files
                    and isinstance(source_files[-1], dict)
                    else {}
                )
                solutions.append(
                    {
                        "canonical_key": canonical_key,
                        "language": language,
                        "source_code": code,
                        "explanation": str(
                            hosted_row.get("explanation_markdown") or ""
                        )
                        or None,
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
                )

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
                "title": str(hosted_row.get("title") or slug.replace("-", " ").title()),
                "slug": f"leetcode-{slug}",
                "description": str(hosted_row.get("problem_markdown") or "") or None,
                "difficulty": _difficulty(hosted_row.get("difficulty")),
                "source_url": str(
                    hosted_row.get("source_url")
                    or f"https://leetcode.com/problems/{slug}/"
                ),
                "topics": hosted_row.get("topics")
                if isinstance(hosted_row.get("topics"), list)
                else [],
                "source_name": "uploaded-source-backed-question-bank",
                "source_path": f"hosted_question_candidates.jsonl#{slug}",
                "source_hash": _hash(hosted_row),
                "disposition": "external_reference_only",
            }
        )
        language = _language(hosted_row.get("reference_solution_language"))
        code = str(hosted_row.get("reference_solution_code") or "")
        if language and code.strip():
            source_files = hosted_row.get("source_files")
            solution_source = (
                source_files[-1]
                if isinstance(source_files, list)
                and source_files
                and isinstance(source_files[-1], dict)
                else {}
            )
            solutions.append(
                {
                    "canonical_key": canonical_key,
                    "language": language,
                    "source_code": code,
                    "explanation": str(
                        hosted_row.get("explanation_markdown") or ""
                    )
                    or None,
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
            )

    articles: list[dict[str, object]] = []
    for row in system_design:
        body = str(row.get("markdown") or "")
        if not body.strip():
            continue
        articles.append(
            {
                "slug": f"uploaded-{row['slug']}",
                "title": str(row.get("title") or row["slug"]),
                "body": body,
                "headings": _headings(body),
                "image_paths": [],
                "source_name": str(
                    row.get("source_archive") or "uploaded-system-design-notes"
                ),
                "source_path": str(
                    row.get("source_path") or f"system_design_resources.jsonl#{row['slug']}"
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
    if counts["problems"] != 3425:
        raise ValueError(f"expected 3425 problems, found {counts['problems']}")
    if counts["solutions"] != 120:
        raise ValueError(f"expected 120 solutions, found {counts['solutions']}")
    if counts["system_design_articles"] != 29:
        raise ValueError(
            f"expected 29 system-design articles, found {counts['system_design_articles']}"
        )
    if counts["company_observations"] < 35_000:
        raise ValueError(
            "expected at least 35,000 company observations, "
            f"found {counts['company_observations']}"
        )
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
