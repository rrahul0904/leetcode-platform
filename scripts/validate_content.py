#!/usr/bin/env python3
"""Deterministic validation for manifest and structured content packages."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from pydantic import ValidationError
from rigor_question_schema import QuestionPackage, SolutionPackage

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "content" / "question-bank-manifest.json"
QUESTION_ROOT = ROOT / "content" / "questions"
EXPECTED_TRACKS = {
    "python-engineering": 150,
    "sql-analytics": 150,
    "data-modeling": 100,
    "data-architecture": 120,
    "distributed-systems": 150,
    "system-design": 160,
    "ml-system-design": 100,
    "generative-ai-architecture": 140,
    "ai-infrastructure": 90,
    "ai-safety-agents-evaluation": 80,
    "staff-principal-leadership": 60,
    "behavioral-execution": 50,
}
EXPECTED_DIFFICULTIES = {
    "foundational": 135,
    "intermediate": 270,
    "advanced": 473,
    "staff": 337,
    "principal": 135,
}
REQUIRED = {
    "id",
    "working_title",
    "slug",
    "primary_track",
    "skills",
    "difficulty",
    "role_level",
    "company_style_tags",
    "learning_objective",
    "estimated_duration_minutes",
    "content_status",
}


def validate_manifest() -> list[str]:
    errors: list[str] = []
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    questions = data.get("questions", [])
    if len(questions) != 1350:
        errors.append(f"expected 1350 entries; found {len(questions)}")

    identifiers: list[str] = []
    slugs: list[str] = []
    titles: list[str] = []
    tracks: Counter[str] = Counter()
    difficulties: Counter[str] = Counter()
    for position, question in enumerate(questions):
        missing = REQUIRED - question.keys()
        if missing:
            errors.append(f"entry {position} missing {sorted(missing)}")
            continue
        identifiers.append(question["id"])
        slugs.append(question["slug"])
        titles.append(question["working_title"])
        tracks[question["primary_track"]] += 1
        difficulties[question["difficulty"]] += 1
        if question["content_status"] != "planned":
            errors.append(f"{question['id']} must begin in planned state")
        if not question["skills"] or not question["company_style_tags"]:
            errors.append(f"{question['id']} has empty skills or company tags")

    for field_name, values in (("ID", identifiers), ("slug", slugs), ("title", titles)):
        duplicates = [value for value, count in Counter(values).items() if count > 1]
        if duplicates:
            errors.append(f"duplicate {field_name} values: {duplicates[:5]}")

    if dict(tracks) != EXPECTED_TRACKS:
        errors.append(f"track distribution mismatch: {dict(tracks)}")
    if dict(difficulties) != EXPECTED_DIFFICULTIES:
        errors.append(f"difficulty distribution mismatch: {dict(difficulties)}")
    return errors


def validate_packages(package_roots: list[Path] | None = None) -> tuple[list[str], int]:
    errors: list[str] = []
    validated = 0
    roots = package_roots or [QUESTION_ROOT]
    for package_root in roots:
        for question_path in sorted(package_root.glob("**/question.json")):
            package_dir = question_path.parent
            required_paths = {
                "solution": package_dir / "solution.json",
                "rubric": package_dir / "rubric.json",
                "metadata": package_dir / "metadata.json",
                "public_tests": package_dir / "tests" / "public.json",
                "hidden_tests": package_dir / "tests" / "hidden.json",
            }
            missing = [name for name, path in required_paths.items() if not path.exists()]
            if missing:
                errors.append(f"{package_dir.name}: missing sidecars {missing}")
                continue
            try:
                question = json.loads(question_path.read_text(encoding="utf-8"))
                rubric = json.loads(required_paths["rubric"].read_text(encoding="utf-8"))
                metadata = json.loads(required_paths["metadata"].read_text(encoding="utf-8"))
                public_tests = json.loads(
                    required_paths["public_tests"].read_text(encoding="utf-8")
                )
                hidden_tests = json.loads(
                    required_paths["hidden_tests"].read_text(encoding="utf-8")
                )
                question["evaluation_rubric"] = rubric
                question.update(metadata)
                mode = question["mode_specification"]
                if "runtime" in mode or "dialect" in mode:
                    mode["tests"] = [*public_tests, *hidden_tests]
                QuestionPackage.model_validate(question)
                SolutionPackage.model_validate_json(
                    required_paths["solution"].read_text(encoding="utf-8")
                )
            except (json.JSONDecodeError, ValidationError, KeyError, TypeError) as exc:
                errors.append(f"{package_dir.name}: {exc}")
            else:
                validated += 1
    return errors, validated


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest-only", action="store_true")
    parser.add_argument(
        "--extra-package-root",
        action="append",
        type=Path,
        default=[],
        help="Additional review/quarantine package tree to schema-validate.",
    )
    args = parser.parse_args()
    errors = validate_manifest()
    package_count = 0
    if not args.manifest_only:
        package_roots = [QUESTION_ROOT, *args.extra_package_root]
        package_errors, package_count = validate_packages(package_roots)
        errors.extend(package_errors)
    if errors:
        print("content validation failed")
        for error in errors:
            print(f"- {error}")
        return 1
    print(
        "content validation passed: "
        f"1,350 planned manifest entries; {package_count} schema-complete package(s); 0 published"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
