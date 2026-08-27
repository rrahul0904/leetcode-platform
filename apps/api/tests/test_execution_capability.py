from __future__ import annotations

from uuid import uuid4

from rigor_api.execution_capability import _capability


def _payload(mode: dict[str, object], *, question_type: str = "python_coding") -> dict[str, object]:
    return {
        "question_version_id": uuid4(),
        "structured_content": {
            "question_type": question_type,
            "mode_specification": mode,
        },
    }


def test_python_question_with_entrypoint_and_tests_is_runnable() -> None:
    capability = _capability(
        _payload(
            {
                "runtime": "python3.13",
                "entrypoint": "solve",
                "starter_code": "def solve(value):\n    return value\n",
                "tests": [
                    {"id": "public-1", "visibility": "public"},
                    {"id": "hidden-1", "visibility": "hidden"},
                ],
            }
        )
    )

    assert capability.availability == "runnable"
    assert capability.runtime == "python3.13"
    assert capability.public_test_count == 1
    assert capability.hidden_test_count == 1
    assert capability.reason is None


def test_zero_test_question_is_hosted_only() -> None:
    capability = _capability(
        _payload(
            {
                "runtime": "python3.13",
                "entrypoint": "solve",
                "starter_code": "def solve(value):\n    return value\n",
                "tests": [],
            }
        )
    )

    assert capability.availability == "hosted"
    assert capability.runtime == "python3.13"
    assert capability.public_test_count == 0
    assert capability.hidden_test_count == 0
    assert "No deterministic execution tests" in (capability.reason or "")


def test_unsupported_runtime_is_hosted_only() -> None:
    capability = _capability(
        _payload(
            {
                "runtime": "pyspark",
                "starter_code": "def solve(value):\n    return value\n",
                "tests": [{"id": "public-1", "visibility": "public"}],
            },
            question_type="pyspark_coding",
        )
    )

    assert capability.availability == "hosted"
    assert capability.runtime is None
    assert "supported executable runtime" in (capability.reason or "")


def test_sql_without_fixture_schema_is_hosted_only() -> None:
    capability = _capability(
        _payload(
            {
                "dialect": "postgresql18",
                "tests": [{"id": "public-1", "visibility": "public"}],
            },
            question_type="sql_coding",
        )
    )

    assert capability.availability == "hosted"
    assert capability.runtime == "postgresql18"
    assert "isolated fixture schema" in (capability.reason or "")
