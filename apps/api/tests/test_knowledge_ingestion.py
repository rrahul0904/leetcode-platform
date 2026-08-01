from __future__ import annotations

import csv
import shutil
import zipfile
from pathlib import Path

import pytest

from rigor_api.knowledge_ingestion import (
    ArchiveSafetyError,
    SourceDisposition,
    inspect_archive,
    inventory_archives,
    merge_bundles,
    parse_repository,
)


def _write_zip(path: Path, members: dict[str, str]) -> None:
    with zipfile.ZipFile(path, "w") as archive:
        for name, value in members.items():
            archive.writestr(name, value)


def test_inventory_detects_exact_duplicate_archives(tmp_path: Path) -> None:
    members = {"repo/1. Two Sum/README.md": "# Two Sum\n"}
    first = tmp_path / "first.zip"
    _write_zip(first, members)
    shutil.copyfile(first, tmp_path / "second.zip")

    records = inventory_archives(tmp_path)

    assert len(records) == 2
    assert records[0].archive_sha256 == records[1].archive_sha256
    assert records[0].duplicate_of is None
    assert records[1].duplicate_of == "first.zip"


def test_archive_rejects_path_traversal(tmp_path: Path) -> None:
    archive = tmp_path / "unsafe.zip"
    _write_zip(archive, {"../escape.txt": "not allowed"})

    with pytest.raises(ArchiveSafetyError, match="Unsafe archive path"):
        inspect_archive(archive)


def test_problem_folder_parser_collects_python_and_javascript(
    tmp_path: Path,
) -> None:
    problem = tmp_path / "Algorithms" / "src" / "1. Two Sum"
    (problem / "Explanation").mkdir(parents=True)
    (problem / "Code").mkdir()
    (problem / "Explanation" / "explanation.md").write_text(
        """# Two Sum

## Problem Description
Return the indexes of two values whose sum equals the target.

## Topics
Array, Hash Table

Time Complexity: O(n)
Space Complexity: O(n)
""",
        encoding="utf-8",
    )
    (problem / "Code" / "solution.py").write_text(
        "def two_sum(nums, target):\n    return []\n",
        encoding="utf-8",
    )
    (problem / "Code" / "solution.js").write_text(
        "function twoSum(nums, target) { return []; }\n",
        encoding="utf-8",
    )

    bundle = parse_repository(
        tmp_path,
        source_name="LeetCode-Solutions-main",
        disposition=SourceDisposition.HOSTABLE_LICENSED,
    )

    assert len(bundle.problems) == 1
    assert bundle.problems[0].canonical_key == "leetcode:1"
    assert bundle.problems[0].title == "Two Sum"
    assert set(bundle.problems[0].topics) >= {"array", "hashing"}
    assert {(item.language, item.canonical_key) for item in bundle.solutions} == {
        ("python", "leetcode:1"),
        ("javascript", "leetcode:1"),
    }


def test_company_csv_parser_supports_uploaded_formats(tmp_path: Path) -> None:
    company_dir = tmp_path / "Amazon"
    company_dir.mkdir()
    path = company_dir / "1. Thirty Days.csv"
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(
            [
                "ID",
                "Title",
                "Acceptance",
                "Difficulty",
                "Frequency",
                "Leetcode Question Link",
            ]
        )
        writer.writerow(
            [
                "1",
                "Two Sum",
                "55.2%",
                "Easy",
                "87.4",
                "https://leetcode.com/problems/two-sum/",
            ]
        )

    bundle = parse_repository(
        tmp_path,
        source_name="LeetCode-Questions-CompanyWise-master",
        disposition=SourceDisposition.EXTERNAL_REFERENCE_ONLY,
    )

    assert len(bundle.companies) == 1
    item = bundle.companies[0]
    assert item.canonical_key == "leetcode:1"
    assert item.company == "Amazon"
    assert item.difficulty == "easy"
    assert item.acceptance_rate == 55.2
    assert item.frequency == 87.4


def test_merge_preserves_unique_solutions_and_one_problem(
    tmp_path: Path,
) -> None:
    first = tmp_path / "first" / "1. Two Sum"
    second = tmp_path / "second" / "1. Two Sum"
    first.mkdir(parents=True)
    second.mkdir(parents=True)
    (first / "README.md").write_text(
        "# Two Sum\nShort description.\n",
        encoding="utf-8",
    )
    (first / "solution.py").write_text(
        "def solve(value): return value\n",
        encoding="utf-8",
    )
    (second / "README.md").write_text(
        "# Two Sum\nA much more complete description with examples and constraints.\n",
        encoding="utf-8",
    )
    (second / "solution.js").write_text(
        "function solve(value) { return value; }\n",
        encoding="utf-8",
    )

    first_bundle = parse_repository(
        tmp_path / "first",
        source_name="first",
        disposition=SourceDisposition.HOSTABLE_LICENSED,
    )
    second_bundle = parse_repository(
        tmp_path / "second",
        source_name="second",
        disposition=SourceDisposition.HOSTABLE_LICENSED,
    )

    merged = merge_bundles([first_bundle, second_bundle])

    assert len(merged.problems) == 1
    assert "much more complete" in (merged.problems[0].description or "")
    assert {item.language for item in merged.solutions} == {
        "python",
        "javascript",
    }
