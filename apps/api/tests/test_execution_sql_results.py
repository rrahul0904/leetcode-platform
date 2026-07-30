from __future__ import annotations

import json
from uuid import UUID

from rigor_api.execution_results import SandboxExecutionResult, trusted_compare

EXECUTION_ID = UUID("55555555-5555-5555-5555-555555555555")


def _sandbox(actual: object, *, visibility: str = "public") -> SandboxExecutionResult:
    return SandboxExecutionResult(
        execution_id=EXECUTION_ID,
        attempt=1,
        status="COMPLETED",
        runtime_ms=5,
        exit_code=0,
        tests=[
            {
                "id": "sql-1",
                "visibility": visibility,
                "ok": True,
                "actual": actual,
                "error_category": None,
            }
        ],
        stdout="",
        stderr="",
        error_category=None,
    )


def _expected(
    rows: list[dict[str, object]],
    *,
    strategy: str,
    visibility: str = "public",
) -> dict[str, dict[str, object]]:
    return {
        "sql-1": {
            "id": "sql-1",
            "name": "SQL result",
            "visibility": visibility,
            "expected_output": rows,
            "expected_columns": ["department", "employees"],
            "comparison": {"strategy": strategy},
        }
    }


def test_sql_ordered_comparison_preserves_row_order_and_column_order() -> None:
    actual = {
        "columns": ["department", "employees"],
        "rows": [["AI", 2], ["Data", 1]],
    }
    expected_rows = [
        {"department": "AI", "employees": 2},
        {"department": "Data", "employees": 1},
    ]

    assert trusted_compare(_sandbox(actual), _expected(expected_rows, strategy="sql_ordered")).all_tests_passed

    reversed_actual = {
        "columns": ["department", "employees"],
        "rows": [["Data", 1], ["AI", 2]],
    }
    assert not trusted_compare(
        _sandbox(reversed_actual),
        _expected(expected_rows, strategy="sql_ordered"),
    ).all_tests_passed

    swapped_columns = {
        "columns": ["employees", "department"],
        "rows": [[2, "AI"], [1, "Data"]],
    }
    assert not trusted_compare(
        _sandbox(swapped_columns),
        _expected(expected_rows, strategy="sql_ordered"),
    ).all_tests_passed


def test_sql_unordered_comparison_accepts_row_reordering_but_preserves_duplicates() -> None:
    expected_rows = [
        {"department": "AI", "employees": 2},
        {"department": "AI", "employees": 2},
        {"department": "Data", "employees": 1},
    ]
    reordered_actual = {
        "columns": ["department", "employees"],
        "rows": [["Data", 1], ["AI", 2], ["AI", 2]],
    }

    assert trusted_compare(
        _sandbox(reordered_actual),
        _expected(expected_rows, strategy="sql_unordered"),
    ).all_tests_passed

    missing_duplicate = {
        "columns": ["department", "employees"],
        "rows": [["Data", 1], ["AI", 2]],
    }
    assert not trusted_compare(
        _sandbox(missing_duplicate),
        _expected(expected_rows, strategy="sql_unordered"),
    ).all_tests_passed


def test_hidden_sql_expected_rows_never_enter_public_projection() -> None:
    actual = {
        "columns": ["department", "employees"],
        "rows": [["Secret", 99]],
    }
    expected_rows = [{"department": "Secret", "employees": 99}]

    projection = trusted_compare(
        _sandbox(actual, visibility="hidden"),
        _expected(expected_rows, strategy="sql_ordered", visibility="hidden"),
    )

    assert projection.hidden_total == 1
    assert projection.hidden_passed == 1
    assert projection.public_results == []
    assert "Secret" not in json.dumps(projection.public_results)
    assert projection.all_tests_passed


def test_sql_result_normalization_preserves_nulls_and_numeric_values() -> None:
    sandbox = SandboxExecutionResult(
        execution_id=EXECUTION_ID,
        attempt=1,
        status="COMPLETED",
        runtime_ms=5,
        exit_code=0,
        tests=[
            {
                "id": "sql-1",
                "visibility": "public",
                "ok": True,
                "actual": {"columns": ["value", "note"], "rows": [[3.5, None]]},
                "error_category": None,
            }
        ],
        stdout="",
        stderr="",
        error_category=None,
    )
    expected = {
        "sql-1": {
            "id": "sql-1",
            "name": "numeric/null",
            "visibility": "public",
            "expected_output": [{"value": 3.5, "note": None}],
            "expected_columns": ["value", "note"],
            "comparison": {"strategy": "sql_ordered"},
        }
    }

    assert trusted_compare(sandbox, expected).all_tests_passed
