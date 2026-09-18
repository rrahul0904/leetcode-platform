from __future__ import annotations

from rigor_api.execution import LocalFunctionalPythonRunner
from rigor_api.schemas import SubmissionRuntime
from scripts.build_attachment_execution_bank import python_spec, sql_spec


def test_python_execution_bank_builds_public_and_hidden_tests() -> None:
    row = {
        "solution": "def solve(scores, target):\n    for i, a in enumerate(scores):\n        for j in range(i + 1, len(scores)):\n            if a + scores[j] == target:\n                return [i, j]\n    return [-1, -1]\n",
        "example": "scores=[4, 11, 6, 9], target=15 -> [0,1]",
    }
    specification, status = python_spec(row)
    assert status == "ready"
    assert specification is not None
    tests = specification["tests"]
    assert any(test["visibility"] == "public" for test in tests)
    assert any(test["visibility"] == "hidden" for test in tests)


def test_python_runner_accepts_multi_argument_solve_input() -> None:
    runner = LocalFunctionalPythonRunner()
    result = runner.execute(
        SubmissionRuntime.python,
        "def solve(a, b):\n    return a + b\n",
        [
            {
                "id": "public-1",
                "name": "two arguments",
                "visibility": "public",
                "input": {"a": 2, "b": 3},
                "expected_output": 5,
            },
            {
                "id": "hidden-1",
                "name": "hidden two arguments",
                "visibility": "hidden",
                "input": {"a": -3, "b": 8},
                "expected_output": 5,
            },
        ],
    )
    assert result.status == "passed"
    assert result.public_results[0].passed is True
    assert result.hidden_summary.total == 1
    assert result.hidden_summary.passed == 1


def test_sql_builder_requires_complete_declared_schema() -> None:
    row = {
        "subject": "SQL",
        "question_type": "sql_coding",
        "input_output_or_schema": "```sql\nCREATE TABLE facts (id INT, amount INT);\n```",
        "solution": "```sql\nSELECT COUNT(*) AS n FROM facts WHERE amount >= 20;\n```",
    }
    specification, status = sql_spec(row)
    assert status == "ready_precheck"
    assert specification is not None
    assert specification["challenge"]["ddl"]
    assert specification["challenge"]["seed_data"]
    assert any(test["visibility"] == "public" for test in specification["tests"])
    assert any(test["visibility"] == "hidden" for test in specification["tests"])


def test_sql_builder_fails_closed_for_undeclared_table() -> None:
    row = {
        "subject": "SQL",
        "question_type": "sql_coding",
        "input_output_or_schema": "```sql\nCREATE TABLE facts (id INT, amount INT);\n```",
        "solution": "```sql\nSELECT * FROM missing_dimension;\n```",
    }
    specification, status = sql_spec(row)
    assert specification is None
    assert status == "reference_uses_undeclared_tables"
