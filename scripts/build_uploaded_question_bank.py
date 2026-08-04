#!/usr/bin/env python3
"""Build normalized Rigor question-bank indexes from uploaded ZIP archives."""

from __future__ import annotations

import argparse
import collections
import csv
import io
import json
import pathlib
import re
import zipfile
from typing import Any

TEXT_EXTENSIONS = {".md", ".py", ".cpp", ".java", ".js", ".go", ".c", ".c++", ".kt", ".cs", ".dart"}
PREFERRED_LANGUAGES = ["py", "cpp", "c++", "java", "js", "go", "c", "kt", "cs", "dart"]


def slugify(value: str) -> str:
    value = (value or "").strip().lower()
    match = re.search(r"leetcode\.com/problems/([^/?#]+)", value)
    if match:
        return match.group(1)
    value = re.sub(r"^\d+[._\s-]+", "", value)
    return re.sub(r"[^a-z0-9]+", "-", value).strip("-")


def write_jsonl(path: pathlib.Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as stream:
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")


def build(archives: list[pathlib.Path], output: pathlib.Path) -> dict[str, int]:
    output.mkdir(parents=True, exist_ok=True)
    company_records: dict[str, dict[str, Any]] = collections.defaultdict(
        lambda: {
            "title": "",
            "difficulty": "",
            "topics": set(),
            "companies": collections.defaultdict(dict),
            "links": set(),
            "sources": set(),
        }
    )
    seen_rows: set[tuple[str, ...]] = set()

    for archive in archives:
        with zipfile.ZipFile(archive) as bundle:
            for item in bundle.infolist():
                if item.is_dir() or not item.filename.lower().endswith(".csv"):
                    continue
                text = bundle.read(item).decode("utf-8-sig", errors="replace")
                parts = pathlib.PurePosixPath(item.filename).parts
                company = parts[-2] if len(parts) >= 3 else None
                window = pathlib.PurePosixPath(parts[-1]).stem
                if len(parts) < 3:
                    match = re.match(r"(.+?)_(6months|1year|2year|alltime)$", window, re.I)
                    if match:
                        company, window = match.group(1), match.group(2)
                for source_row in csv.DictReader(io.StringIO(text)):
                    title = (source_row.get("Title") or source_row.get("title") or "").strip()
                    link = (source_row.get("Link") or source_row.get("link") or "").strip()
                    slug = slugify(link or title)
                    if not slug:
                        continue
                    difficulty = (source_row.get("Difficulty") or source_row.get("difficulty") or "").strip().upper()
                    topics = (source_row.get("Topics") or "").strip()
                    frequency = (source_row.get("Frequency") or "").strip()
                    signature = (slug, company or "", window or "", frequency, difficulty, topics)
                    if signature in seen_rows:
                        continue
                    seen_rows.add(signature)
                    record = company_records[slug]
                    record["title"] = record["title"] or title
                    record["difficulty"] = record["difficulty"] or difficulty
                    if topics:
                        record["topics"].update(topic.strip() for topic in topics.split(",") if topic.strip())
                    if link:
                        record["links"].add(link)
                    record["sources"].add(archive.name)
                    if company:
                        record["companies"][company][window or "unknown"] = frequency

    statements: dict[str, dict[str, str]] = {}
    explanations: dict[str, dict[str, str]] = {}
    solutions: dict[str, dict[str, list[dict[str, str]]]] = collections.defaultdict(lambda: collections.defaultdict(list))
    system_notes: list[dict[str, Any]] = []

    for archive in archives:
        with zipfile.ZipFile(archive) as bundle:
            for item in bundle.infolist():
                if item.is_dir():
                    continue
                extension = pathlib.PurePosixPath(item.filename).suffix.lower()
                if extension not in TEXT_EXTENSIONS:
                    continue
                content = bundle.read(item).decode("utf-8", errors="replace")
                if extension == ".md":
                    if "system-design-notes-main/" in item.filename and len(content.strip()) > 150:
                        title = pathlib.PurePosixPath(item.filename).parent.name.replace("-", " ")
                        system_notes.append({
                            "id": f"SDN-{len(system_notes) + 1:04d}",
                            "slug": slugify(title),
                            "title": title,
                            "markdown": content,
                            "source_archive": archive.name,
                            "source_path": item.filename,
                        })
                    match = re.search(
                        r"^#\s*\[(?:\d+\.\s*)?([^\]]+)\]\((https?://leetcode\.com/problems/[^)]+)\)",
                        content,
                        re.M | re.I,
                    )
                    if match and len(content) > 200:
                        slug = slugify(match.group(2))
                        statements.setdefault(slug, {
                            "title": match.group(1).strip(),
                            "link": match.group(2),
                            "markdown": content,
                            "source_archive": archive.name,
                            "source_path": item.filename,
                        })
                    elif "/Explanation/" in item.filename:
                        parts = pathlib.PurePosixPath(item.filename).parts
                        if "src" in parts:
                            index = parts.index("src")
                            if index + 1 < len(parts):
                                explanations.setdefault(slugify(parts[index + 1]), {
                                    "markdown": content,
                                    "source_archive": archive.name,
                                    "source_path": item.filename,
                                })
                    continue
                if len(content.strip()) <= 20:
                    continue
                parts = pathlib.PurePosixPath(item.filename).parts
                candidate = None
                if "src" in parts:
                    index = parts.index("src")
                    if index + 1 < len(parts):
                        candidate = parts[index + 1]
                else:
                    for part in reversed(parts[:-1]):
                        if re.match(r"^\d+[._\s-]+", part):
                            candidate = part
                            break
                    candidate = candidate or pathlib.PurePosixPath(item.filename).stem
                slug = slugify(candidate)
                if slug:
                    solutions[slug][extension.lstrip(".")].append({
                        "code": content,
                        "source_archive": archive.name,
                        "source_path": item.filename,
                    })

    external_rows = []
    for slug, record in sorted(company_records.items()):
        external_rows.append({
            "slug": slug,
            "title": record["title"] or slug.replace("-", " ").title(),
            "difficulty": (record["difficulty"] or "UNKNOWN").lower(),
            "topics": sorted(record["topics"]),
            "companies": sorted(record["companies"]),
            "company_frequency": record["companies"],
            "links": sorted(record["links"]),
            "source_archives": sorted(record["sources"]),
            "has_statement": slug in statements,
            "has_solution": slug in solutions,
        })

    hosted_rows = []
    for slug, statement in sorted(statements.items()):
        metadata = company_records.get(slug, {})
        best_language = None
        best_solution = None
        for language in PREFERRED_LANGUAGES:
            if solutions.get(slug, {}).get(language):
                best_language = language
                best_solution = solutions[slug][language][0]
                break
        hosted_rows.append({
            "id": f"IMP-{len(hosted_rows) + 1:04d}",
            "slug": slug,
            "title": statement["title"],
            "difficulty": (metadata.get("difficulty") or "UNKNOWN").lower(),
            "topics": sorted(metadata.get("topics", [])),
            "companies": sorted(metadata.get("companies", {})),
            "company_frequency": metadata.get("companies", {}),
            "source_url": statement["link"],
            "problem_markdown": statement["markdown"],
            "explanation_markdown": explanations.get(slug, {}).get("markdown", ""),
            "reference_solution_language": best_language,
            "reference_solution_code": best_solution["code"] if best_solution else "",
            "status": "imported-draft",
            "runnable": False,
            "validation_notes": "Generate and validate public/hidden tests before hosted publication.",
        })

    write_jsonl(output / "external_question_index.jsonl", external_rows)
    write_jsonl(output / "hosted_question_candidates.jsonl", hosted_rows)
    write_jsonl(output / "system_design_resources.jsonl", system_notes)
    manifest = {
        "archives": len(archives),
        "unique_company_index_questions": len(external_rows),
        "statement_backed_hosted_candidates": len(hosted_rows),
        "hosted_candidates_with_reference_solution": sum(bool(row["reference_solution_code"]) for row in hosted_rows),
        "system_design_resources": len(system_notes),
        "unique_solution_slugs": len(solutions),
        "company_mentions": sum(len(row["companies"]) for row in external_rows),
        "source_csv_rows_after_dedup": len(seen_rows),
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("archives", nargs="+", type=pathlib.Path)
    parser.add_argument("--output", type=pathlib.Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build(args.archives, args.output), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
