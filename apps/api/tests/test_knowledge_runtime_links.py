from __future__ import annotations

from uuid import uuid4

import pytest

from rigor_api.knowledge_runtime_links import (
    RuntimeLinkVerificationError,
    validate_runtime_package,
)
from rigor_api.schemas import SubmissionRuntime


def _python_question(*, hidden: bool = True) -> dict[str, object]:
    tests = [
        {"id": "public-1", "visibility": "public", "input": [1], "expected": 2},
    ]
    if hidden:
        tests.append(
            {"id": "hidden-1", "visibility": "hidden", "input": [5], "expected": 6}
        )
    return {
        "question_version_id": uuid4(),
        "structured_content": {
            "question_type": "python_coding",
            "mode_specification": {
                "runtime": "python3.13",
                "entrypoint": "solve",
                "starter_code": "def solve(value):\n    return value\n",
                "tests": tests,
            },
        },
    }


def _sql_question() -> dict[str, object]:
    return {
        "question_version_id": uuid4(),
        "structured_content": {
            "question_type": "sql_coding",
            "mode_specification": {
                "dialect": "postgresql18",
                "starter_sql": "SELECT 1;",
                "schema_sql": "CREATE TABLE values_table(value integer);",
                "seed_sql": "INSERT INTO values_table(value) VALUES (1), (2);",
                "statement_timeout_ms": 3000,
                "tests": [
                    {"id": "public-1", "visibility": "public", "input": {}},
                    {"id": "hidden-1", "visibility": "hidden", "input": {}},
                ],
            },
        },
    }


def test_python_runtime_package_requires_public_and_hidden_tests() -> None:
    evidence = validate_runtime_package(_python_question())
    assert evidence.runtime is SubmissionRuntime.python
    assert evidence.public_tests == 1
    assert evidence.hidden_tests == 1
    assert len(evidence.package_hash) == 64


def test_python_package_without_hidden_test_cannot_be_verified() -> None:
    with pytest.raises(RuntimeLinkVerificationError, match="hidden test"):
        validate_runtime_package(_python_question(hidden=False))


def test_sql_runtime_package_requires_schema_seed_and_test_contract() -> None:
    evidence = validate_runtime_package(_sql_question())
    assert evidence.runtime is SubmissionRuntime.postgresql
    assert evidence.public_tests == 1
    assert evidence.hidden_tests == 1


def test_sql_package_without_schema_cannot_be_verified() -> None:
    payload = _sql_question()
    structured = payload["structured_content"]
    assert isinstance(structured, dict)
    mode = structured["mode_specification"]
    assert isinstance(mode, dict)
    mode.pop("schema_sql")
    with pytest.raises(RuntimeLinkVerificationError, match="schema DDL"):
        validate_runtime_package(payload)


def test_package_hash_changes_with_hidden_test_contract() -> None:
    first = _python_question()
    second = _python_question()
    first["question_version_id"] = second["question_version_id"]
    second_structured = second["structured_content"]
    assert isinstance(second_structured, dict)
    second_mode = second_structured["mode_specification"]
    assert isinstance(second_mode, dict)
    tests = second_mode["tests"]
    assert isinstance(tests, list)
    hidden = tests[1]
    assert isinstance(hidden, dict)
    hidden["input"] = [999]

    assert validate_runtime_package(first).package_hash != validate_runtime_package(second).package_hash
