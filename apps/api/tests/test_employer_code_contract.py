"""Trusted Python/SQL fixture compatibility and hidden-answer redaction tests.

These tests validate protocol *construction* and comparison only. They DO NOT
claim that an EKS/gVisor executor has been deployed or securely exercised.
"""

from __future__ import annotations

import json
from uuid import uuid4

import pytest
from pydantic import ValidationError

from rigor_api.employer_code_contract import (
    PrivateCodeBundle,
    canonical_bundle_digest,
    trusted_runner_contract,
    verified_code_fixtures,
)
from rigor_api.execution_results import (
    SandboxExecutionResult,
    trusted_compare,
)


def python_bundle() -> PrivateCodeBundle:
    return PrivateCodeBundle.model_validate({
        "schema_version": 2,
        "language": "python",
        "entrypoint": "square",
        "invocation_mode": "single_payload",
        "cases": [
            {
                "case_id": "sample_one", "visibility": "sample",
                "input_data": "2", "expected_output": "4", "points": 0,
            },
            {
                "case_id": "hidden_one", "visibility": "hidden",
                "input_data": "19", "expected_output": "361", "points": 100,
            },
        ],
    })


def sql_bundle() -> PrivateCodeBundle:
    schema = "CREATE TABLE purchases (amount integer)"
    return PrivateCodeBundle.model_validate({
        "schema_version": 2,
        "language": "sql",
        "cases": [
            {
                "case_id": "sample_one", "visibility": "sample",
                "input_data": json.dumps({
                    "schema_sql": schema, "seed_sql": "INSERT INTO purchases VALUES (1)",
                }),
                "expected_output": json.dumps({
                    "columns": ["amount"], "rows": [[1]],
                }),
                "points": 0,
            },
            {
                "case_id": "hidden_one", "visibility": "hidden",
                "input_data": json.dumps({
                    "schema_sql": schema, "seed_sql": "INSERT INTO purchases VALUES (98765)",
                }),
                "expected_output": json.dumps({
                    "columns": ["amount"], "rows": [[98765]],
                }),
                "points": 100,
            },
        ],
    })


def test_python_adapter_matches_runner_contract_without_expected_answers() -> None:
    execution_id = uuid4()
    request, expected = trusted_runner_contract(
        python_bundle(), execution_id=execution_id,
        attempt=2, source_code="def square(x): return x*x",
    )
    assert request["schema_version"] == 1
    assert request["entrypoint"] == "square"
    assert request["invocation_mode"] == "single_payload"
    assert request["tests"] == [
        {"id": "sample_one", "visibility": "public", "input": 2},
        {"id": "hidden_one", "visibility": "hidden", "input": 19},
    ]
    assert "expected" not in json.dumps(request).lower()
    assert "361" not in json.dumps(request)
    assert expected["hidden_one"]["expected_output"] == 361
    assert expected["hidden_one"]["visibility"] == "hidden"


def test_sql_adapter_emits_disposable_runner_protocol_without_answer_keys() -> None:
    request, expected = trusted_runner_contract(
        sql_bundle(), execution_id=uuid4(),
        attempt=1, source_code="SELECT amount FROM purchases",
    )
    assert request["schema_version"] == 1
    assert request["statement_timeout_ms"] == 3000
    assert "CREATE TABLE purchases" in str(request["schema_sql"])
    assert request["tests"][1]["visibility"] == "hidden"
    assert request["tests"][1]["input"]["seed_sql"].endswith("(98765)")
    assert "expected" not in json.dumps(request).lower()
    assert expected["hidden_one"]["expected_output"] == {
        "columns": ["amount"], "rows": [[98765]],
    }
    assert expected["hidden_one"]["comparison"] == {"strategy": "sql_ordered"}


def test_trusted_comparator_uses_private_outputs_and_hides_hidden_result_values() -> None:
    execution_id = uuid4()
    _, expected = trusted_runner_contract(
        python_bundle(), execution_id=execution_id,
        attempt=1, source_code="def square(x): return x*x",
    )
    sample = SandboxExecutionResult(
        execution_id=execution_id,
        attempt=1,
        status="COMPLETED",
        runtime_ms=18,
        exit_code=0,
        tests=[
            {"id": "sample_one", "visibility": "public", "ok": True,
             "actual": 4, "error_category": None},
            {"id": "hidden_one", "visibility": "hidden", "ok": True,
             "actual": 361, "error_category": None},
        ],
        stdout="",
        stderr="",
        error_category=None,
    )
    projection = trusted_compare(sample, expected)
    assert projection.hidden_total == 1
    assert projection.hidden_passed == 1
    assert projection.all_tests_passed
    assert len(projection.public_results) == 1
    assert "361" not in json.dumps(projection.public_results)


def test_python_fixture_rejects_non_json_and_nan_inputs() -> None:
    invalid = python_bundle().model_dump()
    invalid["cases"][1]["input_data"] = "{not-json}"
    with pytest.raises(ValidationError, match="valid finite JSON"):
        PrivateCodeBundle.model_validate(invalid)
    invalid = python_bundle().model_dump()
    invalid["cases"][1]["expected_output"] = "NaN"
    with pytest.raises(ValidationError, match="finite JSON"):
        PrivateCodeBundle.model_validate(invalid)


def test_fixture_json_disallows_duplicate_keys_and_float_overflow() -> None:
    invalid = python_bundle().model_dump()
    invalid["cases"][0]["input_data"] = '{"x":1,"x":2}'
    with pytest.raises(ValidationError, match="unique keys"):
        PrivateCodeBundle.model_validate(invalid)
    invalid["cases"][0]["input_data"] = "1e99999"
    with pytest.raises(ValidationError, match="finite JSON"):
        PrivateCodeBundle.model_validate(invalid)


def test_sql_fixture_requires_replayable_schema_and_structured_rows() -> None:
    invalid = sql_bundle().model_dump()
    invalid["cases"][1]["input_data"] = '"DROP TABLE sensitive"'
    with pytest.raises(ValidationError, match="SQL test input"):
        PrivateCodeBundle.model_validate(invalid)
    invalid = sql_bundle().model_dump()
    invalid["cases"][0]["expected_output"] = '"opaque output"'
    with pytest.raises(ValidationError, match="SQL expected output"):
        PrivateCodeBundle.model_validate(invalid)
    invalid = sql_bundle().model_dump()
    invalid["cases"][0]["expected_output"] = json.dumps({
        "columns": ["amount"], "rows": [[1, 2]],
    })
    with pytest.raises(ValidationError, match="row must match"):
        PrivateCodeBundle.model_validate(invalid)


def test_historical_untyped_cases_are_not_misclassified_as_runnable() -> None:
    bundle = sql_bundle()
    source = "1" * 64
    fixture = {
        "source_sha256": source,
        "bundle_sha256": canonical_bundle_digest(bundle),
        "bundle": bundle.model_dump(),
    }
    questions = [{"number": 1, "kind": "code", "language": "sql", "marks": 100}]
    assert verified_code_fixtures(questions, source, {"code_test_bundles": {"1": fixture}})
    fixture["bundle"]["schema_version"] = 1
    assert not verified_code_fixtures(
        questions, source, {"code_test_bundles": {"1": fixture}},
    )


def test_bad_source_and_attempt_are_rejected_before_sandbox_dispatch() -> None:
    with pytest.raises(ValueError, match="source length"):
        trusted_runner_contract(
            python_bundle(), execution_id=uuid4(), attempt=1,
            source_code="x" * 100001,
        )
    with pytest.raises(ValueError, match="attempt"):
        trusted_runner_contract(
            python_bundle(), execution_id=uuid4(), attempt=0,
            source_code="def square(x): return x*x",
        )
