"""Fail-closed private code-fixture publication checks."""

from __future__ import annotations

import copy
import hashlib
import json

from rigor_api.employer_assessment_routes import _verified_code_fixtures


def reviewed() -> tuple[list[dict], str, dict]:
    questions = [{"number": 1, "kind": "code", "language": "sql", "marks": 100}]
    source_sha = "1" * 64
    bundle = {
        "schema_version": 2,
        "language": "sql",
        "entrypoint": "solve",
        "invocation_mode": "auto",
        "statement_timeout_ms": 3000,
        "cases": [
            {
                "case_id": "sample_one", "visibility": "sample",
                "input_data": json.dumps({
                    "schema_sql": "CREATE TABLE events (event_id INT)",
                    "seed_sql": "INSERT INTO events VALUES (1)",
                }),
                "expected_output": json.dumps({
                    "columns": ["event_id"], "rows": [[1]],
                }),
                "points": 0,
            },
            {
                "case_id": "hidden_one", "visibility": "hidden",
                "input_data": json.dumps({
                    "schema_sql": "CREATE TABLE events (event_id INT)",
                    "seed_sql": "INSERT INTO events VALUES (2)",
                }),
                "expected_output": json.dumps({
                    "columns": ["event_id"], "rows": [[2]],
                }),
                "points": 100,
            },
        ],
    }
    digest = hashlib.sha256(
        json.dumps(bundle, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return questions, source_sha, {
        "code_test_bundles": {"1": {
            "source_sha256": source_sha, "bundle_sha256": digest, "bundle": bundle,
        }}
    }


def test_code_questions_require_private_cases_for_every_question() -> None:
    questions, source_sha, rubric = reviewed()
    assert _verified_code_fixtures(questions, source_sha, rubric)
    assert not _verified_code_fixtures(questions, source_sha, {})
    assert not _verified_code_fixtures([
        *questions,
        {"number": 2, "kind": "code", "language": "python", "marks": 25},
    ], source_sha, rubric)
    assert _verified_code_fixtures(
        [{"number": 1, "kind": "written", "marks": 100}], source_sha, {}
    )


def test_corrupt_language_hash_and_scoring_fail_closed() -> None:
    questions, source_sha, rubric = reviewed()
    for key, value in (
        ("source_sha256", "2" * 64),
        ("bundle_sha256", "3" * 64),
    ):
        modified = copy.deepcopy(rubric)
        modified["code_test_bundles"]["1"][key] = value
        assert not _verified_code_fixtures(questions, source_sha, modified)
    modified = copy.deepcopy(rubric)
    modified["code_test_bundles"]["1"]["bundle"]["language"] = "python"
    assert not _verified_code_fixtures(questions, source_sha, modified)
    modified = copy.deepcopy(rubric)
    modified["code_test_bundles"]["1"]["bundle"]["cases"][1]["points"] = 0
    assert not _verified_code_fixtures(questions, source_sha, modified)


def test_hidden_cases_are_not_optional_or_repeatable() -> None:
    questions, source_sha, rubric = reviewed()
    modified = copy.deepcopy(rubric)
    modified["code_test_bundles"]["1"]["bundle"]["cases"][1]["visibility"] = "sample"
    assert not _verified_code_fixtures(questions, source_sha, modified)
    modified = copy.deepcopy(rubric)
    modified["code_test_bundles"]["1"]["bundle"]["cases"][1]["case_id"] = "sample_one"
    assert not _verified_code_fixtures(questions, source_sha, modified)
