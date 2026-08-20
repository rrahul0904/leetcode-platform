#!/usr/bin/env python3
"""Load the normalized SkillForge/DataForge corpus into Supabase safely.

The importer accepts the governed ingestion bundle produced from the uploaded
question banks. It validates bank hashes, preserves provenance, and keeps
rights-review content out of the published state by default.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
import zipfile
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

BATCH_SIZE = 250
RIGHTS_REVIEW = "rights_review_required"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def batched(items: list[dict[str, Any]], size: int = BATCH_SIZE) -> Iterable[list[dict[str, Any]]]:
    for index in range(0, len(items), size):
        yield items[index : index + size]


def title_case_difficulty(value: str | None) -> str:
    normalized = (value or "medium").strip().lower()
    return {"easy": "Easy", "medium": "Medium", "hard": "Hard"}.get(normalized, "Medium")


def topic_slug(problem: dict[str, Any]) -> str:
    metadata = problem.get("metadata") or {}
    topic = str(metadata.get("topic") or "Data Engineering").strip()
    return topic.lower().replace("&", "and").replace("/", "-").replace(" ", "-")


def question_status(problem: dict[str, Any], publish_cleared: bool) -> str:
    disposition = str(problem.get("disposition") or "").strip().lower()
    if disposition == RIGHTS_REVIEW:
        return "review"
    return "published" if publish_cleared else "review"


def materialize_bundle(bundle: Path) -> tuple[Path, tempfile.TemporaryDirectory[str] | None]:
    if bundle.is_dir():
        return bundle, None
    if not zipfile.is_zipfile(bundle):
        raise SystemExit(f"Bundle is neither a directory nor a zip archive: {bundle}")
    temp = tempfile.TemporaryDirectory(prefix="skillforge-corpus-")
    with zipfile.ZipFile(bundle) as archive:
        archive.extractall(temp.name)
    return Path(temp.name), temp


def load_manifest(root: Path) -> dict[str, Any]:
    candidates = [root / "banks" / "BANK_INDEX.json", root / "BANK_INDEX.json"]
    manifest_path = next((path for path in candidates if path.exists()), None)
    if not manifest_path:
        raise SystemExit("BANK_INDEX.json not found in bundle")
    return json.loads(manifest_path.read_text(encoding="utf-8"))


def validate_banks(root: Path, manifest: dict[str, Any]) -> list[Path]:
    banks_dir = root / "banks" if (root / "banks").exists() else root
    paths: list[Path] = []
    for entry in manifest.get("banks", []):
        if int(entry.get("problems") or 0) == 0:
            continue
        path = banks_dir / entry["file"]
        if not path.exists():
            raise SystemExit(f"Missing bank declared by manifest: {entry['file']}")
        expected = entry.get("sha256")
        actual = sha256_file(path)
        if expected and actual != expected:
            raise SystemExit(f"SHA256 mismatch for {entry['file']}: expected {expected}, got {actual}")
        paths.append(path)
    return paths


def read_records(bank_paths: list[Path]) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]], Counter[str]]:
    problems: list[dict[str, Any]] = []
    solutions: dict[str, dict[str, Any]] = {}
    dispositions: Counter[str] = Counter()
    seen_ids: set[str] = set()
    for path in bank_paths:
        bank = json.loads(path.read_text(encoding="utf-8"))
        for problem in bank.get("problems", []):
            public_id = str(problem.get("external_id") or "").strip()
            canonical_key = str(problem.get("canonical_key") or "").strip()
            if not public_id or not canonical_key:
                raise SystemExit(f"Problem missing external_id/canonical_key in {path.name}")
            if public_id in seen_ids:
                raise SystemExit(f"Duplicate public_id found across banks: {public_id}")
            seen_ids.add(public_id)
            dispositions[str(problem.get("disposition") or "unknown")] += 1
            problems.append(problem)
        for solution in bank.get("solutions", []):
            key = str(solution.get("canonical_key") or "").strip()
            if key:
                solutions[key] = solution
    return problems, solutions, dispositions


def dry_run_report(problems: list[dict[str, Any]], solutions: dict[str, dict[str, Any]], dispositions: Counter[str]) -> dict[str, Any]:
    missing_solution = [p["external_id"] for p in problems if p.get("canonical_key") not in solutions]
    difficulties = Counter(title_case_difficulty(p.get("difficulty")) for p in problems)
    languages = Counter(str(p.get("primary_language") or "text") for p in problems)
    return {
        "problems": len(problems),
        "solutions": len(solutions),
        "missing_solution_count": len(missing_solution),
        "missing_solution_sample": missing_solution[:20],
        "difficulty": dict(sorted(difficulties.items())),
        "language": dict(sorted(languages.items())),
        "disposition": dict(sorted(dispositions.items())),
    }


def require_client():
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        raise SystemExit("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required unless --dry-run is used")
    from supabase import create_client

    return create_client(url, key)


def upsert_lookup_tables(client: Any, problems: list[dict[str, Any]]) -> tuple[dict[str, str], dict[tuple[str, str], str]]:
    topic_rows: dict[str, dict[str, Any]] = {}
    subtopic_rows: dict[tuple[str, str], dict[str, str]] = {}
    for problem in problems:
        metadata = problem.get("metadata") or {}
        topic_name = str(metadata.get("topic") or "Data Engineering").strip()
        slug = topic_slug(problem)
        topic_rows[slug] = {"name": topic_name, "slug": slug}
        subtopic = str(metadata.get("subtopic") or "").strip()
        if subtopic:
            sub_slug = subtopic.lower().replace("&", "and").replace("/", "-").replace(" ", "-")
            subtopic_rows[(slug, sub_slug)] = {"name": subtopic, "slug": sub_slug}

    client.table("topics").upsert(list(topic_rows.values()), on_conflict="slug").execute()
    topic_data = client.table("topics").select("id,slug").in_("slug", list(topic_rows)).execute().data
    topic_ids = {row["slug"]: row["id"] for row in topic_data}

    rows = [
        {"topic_id": topic_ids[topic_slug_value], "name": row["name"], "slug": sub_slug}
        for (topic_slug_value, sub_slug), row in subtopic_rows.items()
    ]
    for batch in batched(rows):
        client.table("subtopics").upsert(batch, on_conflict="topic_id,slug").execute()
    subtopic_ids: dict[tuple[str, str], str] = {}
    if rows:
        sub_data = client.table("subtopics").select("id,topic_id,slug").execute().data
        topic_slug_by_id = {value: key for key, value in topic_ids.items()}
        for row in sub_data:
            topic_slug_value = topic_slug_by_id.get(row["topic_id"])
            if topic_slug_value:
                subtopic_ids[(topic_slug_value, row["slug"])] = row["id"]
    return topic_ids, subtopic_ids


def import_corpus(client: Any, problems: list[dict[str, Any]], solutions: dict[str, dict[str, Any]], publish_cleared: bool) -> dict[str, int]:
    topic_ids, subtopic_ids = upsert_lookup_tables(client, problems)
    question_rows: list[dict[str, Any]] = []
    all_tags: set[str] = set()
    problem_by_id: dict[str, dict[str, Any]] = {}

    for problem in problems:
        metadata = problem.get("metadata") or {}
        topic_slug_value = topic_slug(problem)
        subtopic = str(metadata.get("subtopic") or "").strip()
        sub_slug = subtopic.lower().replace("&", "and").replace("/", "-").replace(" ", "-") if subtopic else ""
        public_id = str(problem["external_id"])
        problem_by_id[public_id] = problem
        tags = sorted({str(tag).strip().lower() for tag in problem.get("topics", []) if str(tag).strip()})
        all_tags.update(tags)
        question_rows.append({
            "public_id": public_id,
            "title": str(problem.get("title") or public_id),
            "topic_id": topic_ids.get(topic_slug_value),
            "subtopic_id": subtopic_ids.get((topic_slug_value, sub_slug)) if sub_slug else None,
            "difficulty": title_case_difficulty(problem.get("difficulty")),
            "question_type": str(metadata.get("question_type") or "Scenario"),
            "body": str(problem.get("description") or ""),
            "status": question_status(problem, publish_cleared),
            "primary_language": str(problem.get("primary_language") or "text"),
            "source_name": problem.get("source_name"),
            "source_path": problem.get("source_path"),
            "source_hash": problem.get("source_hash"),
            "source_metadata": {
                "canonical_key": problem.get("canonical_key"),
                "disposition": problem.get("disposition"),
                "metadata": metadata,
                "topics": tags,
                "source_url": problem.get("source_url"),
                "slug": problem.get("slug"),
            },
        })

    for batch in batched(question_rows):
        client.table("questions").upsert(batch, on_conflict="public_id").execute()

    question_data: list[dict[str, Any]] = []
    for start in range(0, len(question_rows), 500):
        ids = [row["public_id"] for row in question_rows[start : start + 500]]
        question_data.extend(client.table("questions").select("id,public_id").in_("public_id", ids).execute().data)
    question_ids = {row["public_id"]: row["id"] for row in question_data}

    solution_rows: list[dict[str, Any]] = []
    for public_id, problem in problem_by_id.items():
        solution = solutions.get(str(problem.get("canonical_key")))
        if not solution:
            continue
        solution_rows.append({
            "question_id": question_ids[public_id],
            "language": str(solution.get("language") or problem.get("primary_language") or "text"),
            "solution_body": str(solution.get("source_code") or solution.get("explanation") or ""),
            "explanation": str(solution.get("explanation") or ""),
            "time_complexity": solution.get("time_complexity"),
            "space_complexity": solution.get("space_complexity"),
            "common_mistakes": [],
        })
    for batch in batched(solution_rows):
        client.table("solutions").upsert(batch, on_conflict="question_id,language").execute()

    tag_rows = [{"name": tag, "slug": tag} for tag in sorted(all_tags)]
    for batch in batched(tag_rows):
        client.table("tags").upsert(batch, on_conflict="slug").execute()
    tag_data = client.table("tags").select("id,slug").in_("slug", sorted(all_tags)).execute().data if all_tags else []
    tag_ids = {row["slug"]: row["id"] for row in tag_data}

    question_tag_rows: list[dict[str, str]] = []
    for public_id, problem in problem_by_id.items():
        for tag in sorted({str(tag).strip().lower() for tag in problem.get("topics", []) if str(tag).strip()}):
            if tag in tag_ids:
                question_tag_rows.append({"question_id": question_ids[public_id], "tag_id": tag_ids[tag]})
    for batch in batched(question_tag_rows):
        client.table("question_tags").upsert(batch, on_conflict="question_id,tag_id").execute()

    return {
        "questions_upserted": len(question_rows),
        "solutions_upserted": len(solution_rows),
        "tags_upserted": len(tag_rows),
        "question_tags_upserted": len(question_tag_rows),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", type=Path, help="Path to dataforge_repo_ingestion_bundle.zip or extracted directory")
    parser.add_argument("--dry-run", action="store_true", help="Validate and report without writing to Supabase")
    parser.add_argument("--publish-cleared", action="store_true", help="Publish only records whose disposition is not rights_review_required")
    args = parser.parse_args()

    root, temp = materialize_bundle(args.bundle)
    try:
        manifest = load_manifest(root)
        bank_paths = validate_banks(root, manifest)
        problems, solutions, dispositions = read_records(bank_paths)
        report = dry_run_report(problems, solutions, dispositions)
        print(json.dumps(report, indent=2, sort_keys=True))
        if report["missing_solution_count"]:
            raise SystemExit("Corpus validation failed: one or more problems are missing solutions")
        if args.dry_run:
            return
        client = require_client()
        result = import_corpus(client, problems, solutions, args.publish_cleared)
        print(json.dumps(result, indent=2, sort_keys=True))
    finally:
        if temp is not None:
            temp.cleanup()


if __name__ == "__main__":
    main()
