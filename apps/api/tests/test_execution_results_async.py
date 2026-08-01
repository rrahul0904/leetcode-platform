from __future__ import annotations

import json
from uuid import UUID

import pytest

from rigor_api.execution_domain import ExecutionStatus
from rigor_api.execution_results import (
    RESULT_PREFIX,
    TrustedResultError,
    parse_runner_result,
    trusted_compare,
)

EXECUTION_ID = UUID("11111111-2222-3333-4444-555555555555")


def runner_log(payload: dict[str, object]) -> str:
    return "runner booted\n" + RESULT_PREFIX + json.dumps(payload, separators=(",", ":")) + "\n"


def exact_expected(
    *,
    test_id: str,
    name: str,
    visibility: str,
    expected_output: object,
) -> dict[str, object]:
    return {
        "id": test_id,
        "name": name,
        "visibility": visibility,
        "expected_output": expected_output,
        "comparison": {"strategy": "exact"},
    }


def test_runner_result_is_parsed_from_bounded_protocol_record() -> None:
    parsed = parse_runner_result(
        runner_log(
            {
                "schema_version": 1,
                "execution_id": str(EXECUTION_ID),
                "attempt": 2,
                "status": "COMPLETED",
                "runtime_ms": 19,
                "exit_code": 0,
                "tests": [
                    {
                        "id": "public-1",
                        "visibility": "public",
                        "ok": True,
                        "actual": 42,
                        "error_category": None,
                    }
                ],
                "stdout": "hello",
                "stderr": "",
            }
        ),
        execution_id=EXECUTION_ID,
        expected_attempt=2,
    )

    assert parsed.execution_id == EXECUTION_ID
    assert parsed.attempt == 2
    assert parsed.status == "COMPLETED"
    assert parsed.runtime_ms == 19
    assert parsed.tests[0]["actual"] == 42


def test_runner_result_rejects_wrong_execution_identifier() -> None:
    with pytest.raises(TrustedResultError, match="identifier mismatch"):
        parse_runner_result(
            runner_log(
                {
                    "schema_version": 1,
                    "execution_id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
                    "attempt": 1,
                    "status": "COMPLETED",
                    "runtime_ms": 1,
                    "exit_code": 0,
                    "tests": [],
                }
            ),
            execution_id=EXECUTION_ID,
        )


def test_runner_result_rejects_wrong_attempt() -> None:
    with pytest.raises(TrustedResultError, match="attempt mismatch"):
        parse_runner_result(
            runner_log(
                {
                    "schema_version": 1,
                    "execution_id": str(EXECUTION_ID),
                    "attempt": 1,
                    "status": "FAILED",
                    "runtime_ms": 1,
                    "exit_code": 1,
                    "tests": [],
                }
            ),
            execution_id=EXECUTION_ID,
            expected_attempt=2,
        )


def test_trusted_comparator_keeps_hidden_expected_answers_out_of_public_projection() -> None:
    sandbox = parse_runner_result(
        runner_log(
            {
                "schema_version": 1,
                "execution_id": str(EXECUTION_ID),
                "attempt": 1,
                "status": "COMPLETED",
                "runtime_ms": 31,
                "exit_code": 0,
                "tests": [
                    {
                        "id": "public-1",
                        "visibility": "public",
                        "ok": True,
                        "actual": 3,
                    },
                    {
                        "id": "hidden-1",
                        "visibility": "hidden",
                        "ok": True,
                        "actual": 99,
                    },
                ],
                "stdout": "",
                "stderr": "",
            }
        ),
        execution_id=EXECUTION_ID,
        expected_attempt=1,
    )
    expected = {
        "public-1": exact_expected(
            test_id="public-1", name="public", visibility="public", expected_output=3
        ),
        "hidden-1": exact_expected(
            test_id="hidden-1", name="secret", visibility="hidden", expected_output=99
        ),
    }

    projection = trusted_compare(sandbox, expected)

    assert projection.execution_status is ExecutionStatus.completed
    assert projection.public_results == [
        {
            "test_id": "public-1",
            "name": "public",
            "passed": True,
            "expected": 3,
            "actual": 3,
            "error_category": None,
        }
    ]
    assert projection.hidden_total == 1
    assert projection.hidden_passed == 1
    assert "99" not in json.dumps(projection.public_results)
    assert projection.all_tests_passed


def test_completed_result_cannot_omit_hidden_tests() -> None:
    sandbox = parse_runner_result(
        runner_log(
            {
                "schema_version": 1,
                "execution_id": str(EXECUTION_ID),
                "attempt": 1,
                "status": "COMPLETED",
                "runtime_ms": 4,
                "exit_code": 0,
                "tests": [
                    {
                        "id": "public-1",
                        "visibility": "public",
                        "ok": True,
                        "actual": 3,
                    }
                ],
                "stdout": "",
                "stderr": "",
            }
        ),
        execution_id=EXECUTION_ID,
    )
    expected = {
        "public-1": exact_expected(
            test_id="public-1", name="public", visibility="public", expected_output=3
        ),
        "hidden-1": exact_expected(
            test_id="hidden-1", name="secret", visibility="hidden", expected_output=99
        ),
    }

    with pytest.raises(TrustedResultError, match="omitted"):
        trusted_compare(sandbox, expected)


def test_trusted_comparator_supports_server_controlled_numeric_tolerance() -> None:
    sandbox = parse_runner_result(
        runner_log(
            {
                "schema_version": 1,
                "execution_id": str(EXECUTION_ID),
                "attempt": 1,
                "status": "COMPLETED",
                "runtime_ms": 2,
                "exit_code": 0,
                "tests": [
                    {
                        "id": "public-1",
                        "visibility": "public",
                        "ok": True,
                        "actual": 0.3000001,
                    }
                ],
                "stdout": "",
                "stderr": "",
            }
        ),
        execution_id=EXECUTION_ID,
    )
    expected = {
        "public-1": {
            "id": "public-1",
            "name": "numeric",
            "visibility": "public",
            "expected_output": 0.3,
            "comparison": {"strategy": "numeric_tolerance", "tolerance": 0.001},
        }
    }

    assert trusted_compare(sandbox, expected).all_tests_passed


def test_trusted_comparator_detects_visibility_tampering() -> None:
    sandbox = parse_runner_result(
        runner_log(
            {
                "schema_version": 1,
                "execution_id": str(EXECUTION_ID),
                "attempt": 1,
                "status": "COMPLETED",
                "runtime_ms": 1,
                "exit_code": 0,
                "tests": [
                    {
                        "id": "hidden-1",
                        "visibility": "public",
                        "ok": True,
                        "actual": "secret",
                    }
                ],
                "stdout": "",
                "stderr": "",
            }
        ),
        execution_id=EXECUTION_ID,
    )

    with pytest.raises(TrustedResultError, match="visibility"):
        trusted_compare(
            sandbox,
            {
                "hidden-1": exact_expected(
                    test_id="hidden-1",
                    name="hidden",
                    visibility="hidden",
                    expected_output="secret",
                )
            },
        )
