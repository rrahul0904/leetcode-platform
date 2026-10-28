"""Trusted employer coding fixture schema and sandbox protocol adapter.

Only approved employer authors can stage this data. Expected answers MUST remain
on the trusted controller side and never be included in sandbox requests.
No candidate code is executed in this module.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

INVOCATION_MODES = {
    "auto", "keyword_arguments", "positional_arguments",
    "single_payload", "no_arguments",
}
MAX_SOURCE_BYTES = 100_000


class PrivateCodeCase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: str = Field(pattern=r"^[a-z][a-z0-9_-]{2,49}$")
    visibility: Literal["sample", "hidden"]
    input_data: str = Field(max_length=20_000)
    expected_output: str = Field(max_length=20_000)
    points: int = Field(ge=0, le=100)


def _json(text: str, label: str) -> Any:
    try:
        return json.loads(
            text, parse_constant=lambda value: (_ for _ in ()).throw(
                ValueError(f"Invalid JSON constant {value}")
            ),
        )
    except (ValueError, TypeError) as exc:
        raise ValueError(f"{label} must be valid finite JSON") from exc


def _sql_input(value: object) -> dict[str, str]:
    if not isinstance(value, dict):
        raise ValueError("SQL test input must be a JSON object with schema_sql")
    allowed = {"schema_sql", "seed_sql", "setup_sql"}
    if set(value) - allowed:
        raise ValueError("SQL test input contains unsupported fields")
    schema = value.get("schema_sql")
    if not isinstance(schema, str) or not schema.strip():
        raise ValueError("SQL schema_sql must be non-empty")
    if len(schema.encode("utf-8")) > 20_000:
        raise ValueError("SQL schema_sql exceeds fixture limit")
    result: dict[str, str] = {"schema_sql": schema}
    for field in ("seed_sql", "setup_sql"):
        item = value.get(field, "")
        if not isinstance(item, str) or len(item.encode("utf-8")) > 20_000:
            raise ValueError(f"SQL {field} must be bounded text")
        result[field] = item
    return result


def _sql_output(value: object) -> dict[str, object]:
    if not isinstance(value, dict) or set(value) != {"columns", "rows"}:
        raise ValueError("SQL expected output must contain only columns and rows")
    cols = value["columns"]
    rows = value["rows"]
    if (
        not isinstance(cols, list) or not cols or len(cols) > 64
        or any(not isinstance(col, str) or not col for col in cols)
        or len(set(cols)) != len(cols)
        or not isinstance(rows, list) or len(rows) > 1000
    ):
        raise ValueError("SQL expected columns or rows are invalid")
    if any(not isinstance(row, list) or len(row) != len(cols) for row in rows):
        raise ValueError("Every SQL expected row must match the column count")
    return {"columns": cols, "rows": rows}


class PrivateCodeBundle(BaseModel):
    """Version 2 is intentionally incompatible with untyped historical test strings."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[2] = 2
    language: Literal["python", "sql"]
    cases: list[PrivateCodeCase] = Field(min_length=2, max_length=30)
    entrypoint: str = Field(default="solve", pattern=r"^[A-Za-z_][A-Za-z_0-9]{0,79}$")
    invocation_mode: Literal[
        "auto", "keyword_arguments", "positional_arguments",
        "single_payload", "no_arguments",
    ] = "auto"
    statement_timeout_ms: int = Field(default=3000, ge=100, le=30000)

    @model_validator(mode="after")
    def check_cases(self) -> PrivateCodeBundle:
        identifiers = [case.case_id for case in self.cases]
        if len(set(identifiers)) != len(identifiers):
            raise ValueError("Test case identifiers must be unique")
        samples = [case for case in self.cases if case.visibility == "sample"]
        hidden = [case for case in self.cases if case.visibility == "hidden"]
        if not samples or not hidden:
            raise ValueError("Both sample and hidden test cases are required")
        if any(case.points != 0 for case in samples):
            raise ValueError("Public sample test cases must have zero marks")
        if any(case.points < 1 for case in hidden):
            raise ValueError("Confidential hidden cases must have positive marks")
        if self.language == "sql" and (
            self.entrypoint != "solve" or self.invocation_mode != "auto"
        ):
            raise ValueError("SQL assessments do not use Python invocation settings")
        for case in self.cases:
            value = _json(case.input_data, f"{case.case_id} input")
            expected = _json(case.expected_output, f"{case.case_id} expected output")
            if self.language == "sql":
                _sql_input(value)
                _sql_output(expected)
        return self


def canonical_bundle_digest(bundle: PrivateCodeBundle) -> str:
    encoded = json.dumps(
        bundle.model_dump(), sort_keys=True, separators=(",", ":"), allow_nan=False,
    )
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def verified_code_fixtures(
    questions: list[dict[str, Any]], source_sha256: str, rubric: dict[str, Any],
) -> bool:
    """Do not publish unless all code cases match the immutable approved version."""
    code_questions = {
        str(question["number"]): question
        for question in questions if question["kind"] == "code"
    }
    if not code_questions:
        return True
    bundles = rubric.get("code_test_bundles")
    if not isinstance(bundles, dict) or set(bundles) != set(code_questions):
        return False
    for number, question in code_questions.items():
        entry = bundles.get(number)
        if not isinstance(entry, dict) or entry.get("source_sha256") != source_sha256:
            return False
        payload = entry.get("bundle")
        if not isinstance(payload, dict) or payload.get("schema_version") != 2:
            return False
        try:
            bundle = PrivateCodeBundle.model_validate(payload)
        except ValidationError:
            return False
        if bundle.language != question.get("language"):
            return False
        if sum(case.points for case in bundle.cases) != int(question["marks"]):
            return False
        if canonical_bundle_digest(bundle) != entry.get("bundle_sha256"):
            return False
    return True


def trusted_runner_contract(
    bundle: PrivateCodeBundle,
    *,
    execution_id: UUID,
    attempt: int,
    source_code: str,
) -> tuple[dict[str, object], dict[str, dict[str, object]]]:
    """Return (untrusted-sandbox request, private expected map), never combined."""
    if isinstance(attempt, bool) or not isinstance(attempt, int) or attempt < 1:
        raise ValueError("Execution attempt is invalid")
    if not source_code or len(source_code.encode("utf-8")) > MAX_SOURCE_BYTES:
        raise ValueError("Candidate source length is invalid")

    tests: list[dict[str, object]] = []
    expected: dict[str, dict[str, object]] = {}
    for case in bundle.cases:
        visibility = "public" if case.visibility == "sample" else "hidden"
        parsed_input: object = _json(case.input_data, "test input")
        parsed_expected: object = _json(case.expected_output, "expected output")
        if bundle.language == "sql":
            parsed_input = _sql_input(parsed_input)
            parsed_expected = _sql_output(parsed_expected)
        tests.append({
            "id": case.case_id,
            "visibility": visibility,
            "input": parsed_input,
        })
        expected[case.case_id] = {
            "id": case.case_id,
            "name": case.case_id,
            "visibility": visibility,
            "expected_output": parsed_expected,
            "comparison": {
                "strategy": "sql_ordered" if bundle.language == "sql" else "exact"
            },
        }
    request: dict[str, object] = {
        "schema_version": 1,
        "execution_id": str(execution_id),
        "attempt": attempt,
        "source_code": source_code,
        "tests": tests,
    }
    if bundle.language == "python":
        request["entrypoint"] = bundle.entrypoint
        request["invocation_mode"] = bundle.invocation_mode
    else:
        first_input = _sql_input(_json(bundle.cases[0].input_data, "SQL input"))
        request["schema_sql"] = first_input["schema_sql"]
        request["seed_sql"] = first_input["seed_sql"]
        request["statement_timeout_ms"] = bundle.statement_timeout_ms
    return request, expected
