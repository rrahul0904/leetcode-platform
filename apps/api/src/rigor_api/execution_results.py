from __future__ import annotations

import json
import math
from dataclasses import dataclass
from typing import cast
from uuid import UUID

from sqlalchemy import Connection, text

from .execution_domain import (
    TERMINAL_EXECUTION_STATUSES,
    ExecutionRepository,
    ExecutionStatus,
    ExecutionTransitionError,
)

RESULT_PREFIX = "RIGOR_EXECUTION_RESULT:"
MAX_RESULT_LOG_BYTES = 256 * 1024
MAX_RESULT_TESTS = 200
MAX_PUBLIC_STREAM_BYTES = 64 * 1024
SUPPORTED_COMPARISONS = {
    "exact",
    "normalized_text",
    "numeric_tolerance",
    "json",
    "unordered",
    "sql_ordered",
    "sql_unordered",
}


class TrustedResultError(ValueError):
    pass


@dataclass(frozen=True)
class DispatchPackage:
    execution_id: UUID
    organization_id: UUID | None
    candidate_id: UUID
    practice_session_id: UUID
    submission_id: UUID | None
    question_version_id: UUID
    execution_type: str
    runtime: str
    language: str
    source_code: str
    input_payload: dict[str, object]
    limits: dict[str, object]
    trace_id: str
    attempt_count: int


@dataclass(frozen=True)
class SandboxExecutionResult:
    execution_id: UUID
    attempt: int
    status: str
    runtime_ms: int
    exit_code: int
    tests: list[dict[str, object]]
    stdout: str
    stderr: str
    error_category: str | None


@dataclass(frozen=True)
class TrustedExecutionProjection:
    execution_status: ExecutionStatus
    runtime_ms: int
    exit_code: int
    error_category: str | None
    public_results: list[dict[str, object]]
    hidden_total: int
    hidden_passed: int
    stdout: str
    stderr: str
    candidate_message: str

    @property
    def total_tests(self) -> int:
        return len(self.public_results) + self.hidden_total

    @property
    def passed_tests(self) -> int:
        return sum(bool(item["passed"]) for item in self.public_results) + self.hidden_passed

    @property
    def all_tests_passed(self) -> bool:
        return self.total_tests > 0 and self.passed_tests == self.total_tests


def _object_dict(value: object, *, label: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise TrustedResultError(f"{label} must be a JSON object.")
    return cast(dict[str, object], value)


def _optional_object_dict(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        return {}
    return cast(dict[str, object], value)


def _object_list(value: object, *, label: str) -> list[object]:
    if not isinstance(value, list):
        raise TrustedResultError(f"{label} must be a JSON array.")
    return cast(list[object], value)


def _required_string(value: object, *, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise TrustedResultError(f"{label} is missing or invalid.")
    return value


def _optional_string(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


def _nonnegative_int(value: object, *, label: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise TrustedResultError(f"{label} is invalid.")
    return value


def _positive_int(value: object, *, label: str) -> int:
    parsed = _nonnegative_int(value, label=label)
    if parsed < 1:
        raise TrustedResultError(f"{label} must be positive.")
    return parsed


def load_dispatch_package(connection: Connection, execution_id: UUID) -> DispatchPackage:
    row = (
        connection.execute(
            text(
                """
                SELECT er.id,
                       er.organization_id,
                       er.candidate_id,
                       er.practice_session_id,
                       er.submission_id,
                       er.question_version_id,
                       er.execution_type,
                       er.runtime,
                       er.language,
                       er.limits,
                       er.trace_id,
                       er.attempt_count,
                       ep.source_code,
                       ep.input_payload
                FROM execution_requests er
                JOIN execution_payloads ep ON ep.execution_request_id=er.id
                WHERE er.id=:execution_id
                """
            ),
            {"execution_id": execution_id},
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        raise TrustedResultError("Execution payload is unavailable.")
    if row["practice_session_id"] is None:
        raise TrustedResultError("Candidate execution has no practice session.")
    if row["candidate_id"] is None:
        raise TrustedResultError("Candidate execution has no candidate owner.")

    input_payload = _optional_object_dict(cast(object, row["input_payload"]))
    limits = _optional_object_dict(cast(object, row["limits"]))
    return DispatchPackage(
        execution_id=UUID(str(row["id"])),
        organization_id=UUID(str(row["organization_id"])) if row["organization_id"] else None,
        candidate_id=UUID(str(row["candidate_id"])),
        practice_session_id=UUID(str(row["practice_session_id"])),
        submission_id=UUID(str(row["submission_id"])) if row["submission_id"] else None,
        question_version_id=UUID(str(row["question_version_id"])),
        execution_type=str(row["execution_type"]),
        runtime=str(row["runtime"]),
        language=str(row["language"]),
        source_code=str(row["source_code"]),
        input_payload=input_payload,
        limits=limits,
        trace_id=str(row["trace_id"]),
        attempt_count=int(row["attempt_count"]),
    )


def sandbox_request(package: DispatchPackage) -> dict[str, object]:
    tests = _object_list(package.input_payload.get("tests"), label="Execution test input")
    sanitized_tests: list[dict[str, object]] = []
    for raw_test in tests:
        test = _object_dict(raw_test, label="Execution test")
        if "expected_output" in test or "expected" in test:
            raise TrustedResultError("Expected answers must not enter the candidate sandbox.")
        sanitized_tests.append(test)
    if package.attempt_count < 1:
        raise TrustedResultError("Execution must be claimed before sandbox dispatch.")

    request_payload: dict[str, object] = {
        "schema_version": 1,
        "execution_id": str(package.execution_id),
        "attempt": package.attempt_count,
        "source_code": package.source_code,
        "tests": sanitized_tests,
    }
    if package.language == "python":
        request_payload["entrypoint"] = str(package.input_payload.get("entrypoint") or "solve")
        request_payload["invocation_mode"] = str(
            package.input_payload.get("invocation_mode") or "auto"
        )
        return request_payload
    if package.language == "sql":
        schema_sql = package.input_payload.get("schema_sql")
        seed_sql = package.input_payload.get("seed_sql", "")
        timeout_ms = package.input_payload.get("statement_timeout_ms")
        if not isinstance(schema_sql, str) or not schema_sql.strip():
            raise TrustedResultError("SQL dispatch payload is missing trusted schema SQL.")
        if not isinstance(seed_sql, str):
            raise TrustedResultError("SQL dispatch seed SQL is invalid.")
        if not isinstance(timeout_ms, int) or isinstance(timeout_ms, bool):
            raise TrustedResultError("SQL dispatch statement timeout is invalid.")
        request_payload.update(
            {
                "schema_sql": schema_sql,
                "seed_sql": seed_sql,
                "statement_timeout_ms": timeout_ms,
            }
        )
        return request_payload
    raise TrustedResultError("Execution language is unsupported by the sandbox protocol.")


def parse_runner_result(
    log_text: str,
    *,
    execution_id: UUID,
    expected_attempt: int | None = None,
) -> SandboxExecutionResult:
    encoded = log_text.encode("utf-8", errors="replace")
    if len(encoded) > MAX_RESULT_LOG_BYTES:
        raise TrustedResultError("Runner result log exceeds the trusted transport limit.")

    payload: dict[str, object] | None = None
    for line in reversed(log_text.splitlines()):
        if not line.startswith(RESULT_PREFIX):
            continue
        try:
            decoded: object = json.loads(line.removeprefix(RESULT_PREFIX))
        except json.JSONDecodeError as exc:
            raise TrustedResultError("Runner emitted malformed result JSON.") from exc
        payload = _object_dict(decoded, label="Runner result")
        break
    if payload is None:
        raise TrustedResultError("Runner result marker was not found.")
    if payload.get("schema_version") != 1:
        raise TrustedResultError("Unsupported runner result schema version.")
    if payload.get("execution_id") != str(execution_id):
        raise TrustedResultError("Runner result execution identifier mismatch.")

    attempt = _positive_int(payload.get("attempt"), label="Runner execution attempt")
    if expected_attempt is not None and attempt != expected_attempt:
        raise TrustedResultError("Runner result execution attempt mismatch.")

    status = _required_string(payload.get("status"), label="Runner status")
    if status not in {"COMPLETED", "FAILED", "TIMEOUT"}:
        raise TrustedResultError("Runner emitted an unsupported terminal status.")
    raw_tests = _object_list(payload.get("tests"), label="Runner test results")
    if len(raw_tests) > MAX_RESULT_TESTS:
        raise TrustedResultError("Runner test result list exceeds the trusted limit.")

    tests: list[dict[str, object]] = []
    seen: set[str] = set()
    for raw_item in raw_tests:
        item = _object_dict(raw_item, label="Runner test result")
        test_id = _required_string(item.get("id"), label="Runner test id")
        visibility = _required_string(item.get("visibility"), label="Runner test visibility")
        if test_id in seen:
            raise TrustedResultError("Runner test identifiers must be unique.")
        if visibility not in {"public", "hidden"}:
            raise TrustedResultError("Runner test visibility is invalid.")
        seen.add(test_id)
        tests.append(
            {
                "id": test_id,
                "visibility": visibility,
                "ok": bool(item.get("ok")),
                "actual": item.get("actual"),
                "error_category": _optional_string(item.get("error_category")),
            }
        )

    runtime_ms = _nonnegative_int(payload.get("runtime_ms"), label="Runner runtime")
    exit_code_value = payload.get("exit_code")
    if not isinstance(exit_code_value, int) or isinstance(exit_code_value, bool):
        raise TrustedResultError("Runner exit code is invalid.")
    stdout = str(payload.get("stdout") or "")[:MAX_PUBLIC_STREAM_BYTES]
    stderr = str(payload.get("stderr") or "")[:MAX_PUBLIC_STREAM_BYTES]
    return SandboxExecutionResult(
        execution_id=execution_id,
        attempt=attempt,
        status=status,
        runtime_ms=runtime_ms,
        exit_code=exit_code_value,
        tests=tests,
        stdout=stdout,
        stderr=stderr,
        error_category=_optional_string(payload.get("error_category")),
    )


def _question_mode(structured: dict[str, object]) -> dict[str, object]:
    for key in ("mode_specification", "type_specification"):
        value = structured.get(key)
        if isinstance(value, dict):
            return cast(dict[str, object], value)
    raise TrustedResultError("Question execution mode is unavailable.")


def _is_sql_mode(structured: dict[str, object], mode: dict[str, object]) -> bool:
    question_type = structured.get("question_type")
    dialect = mode.get("dialect")
    return question_type == "sql_coding" or dialect in {"postgresql", "postgresql18"}


def _comparison_policy(
    item: dict[str, object],
    *,
    default_strategy: str,
) -> dict[str, object]:
    raw = item.get("comparison")
    if raw is None:
        return {"strategy": default_strategy}
    if isinstance(raw, str):
        strategy = raw
        policy: dict[str, object] = {"strategy": strategy}
    elif isinstance(raw, dict):
        policy = cast(dict[str, object], raw)
        strategy = str(policy.get("strategy") or default_strategy)
    else:
        raise TrustedResultError("Question comparison policy is invalid.")
    if default_strategy.startswith("sql_"):
        if strategy == "ordered":
            strategy = "sql_ordered"
        elif strategy == "unordered":
            strategy = "sql_unordered"
    if strategy not in SUPPORTED_COMPARISONS:
        raise TrustedResultError(f"Unsupported trusted comparison strategy {strategy!r}.")
    return {**policy, "strategy": strategy}


def load_expected_tests(
    connection: Connection,
    *,
    question_version_id: UUID,
) -> dict[str, dict[str, object]]:
    structured_value = connection.execute(
        text("SELECT structured_content FROM question_versions WHERE id=:id"),
        {"id": question_version_id},
    ).scalar_one_or_none()
    structured = _object_dict(cast(object, structured_value), label="Question structured content")
    mode = _question_mode(structured)
    default_strategy = "sql_ordered" if _is_sql_mode(structured, mode) else "exact"

    raw_tests = mode.get("tests")
    if not isinstance(raw_tests, list):
        raise TrustedResultError("Question expected tests are unavailable.")
    expected: dict[str, dict[str, object]] = {}
    for raw_test in cast(list[object], raw_tests):
        test = _object_dict(raw_test, label="Expected test")
        test_id = _required_string(test.get("id"), label="Expected test id")
        if test_id in expected:
            raise TrustedResultError("Expected test identifiers must be unique.")
        expected[test_id] = {
            "visibility": str(test.get("visibility") or "hidden"),
            "expected": test.get("expected_output"),
            "comparison": _comparison_policy(test, default_strategy=default_strategy),
        }
    return expected


def _normalize_text(value: object) -> str:
    return "\n".join(line.rstrip() for line in str(value).strip().splitlines())


def _compare(actual: object, expected: object, policy: dict[str, object]) -> bool:
    strategy = str(policy.get("strategy") or "exact")
    if strategy == "exact":
        return actual == expected
    if strategy == "normalized_text":
        return _normalize_text(actual) == _normalize_text(expected)
    if strategy == "numeric_tolerance":
        if isinstance(actual, bool) or isinstance(expected, bool):
            return False
        if not isinstance(actual, (int, float)) or not isinstance(expected, (int, float)):
            return False
        absolute = float(policy.get("absolute_tolerance") or 0.0)
        relative = float(policy.get("relative_tolerance") or 0.0)
        return math.isclose(float(actual), float(expected), abs_tol=absolute, rel_tol=relative)
    if strategy == "json":
        return actual == expected
    if strategy == "unordered":
        if not isinstance(actual, list) or not isinstance(expected, list):
            return False
        return sorted(map(repr, actual)) == sorted(map(repr, expected))
    if strategy in {"sql_ordered", "sql_unordered"}:
        if not isinstance(actual, dict) or not isinstance(expected, dict):
            return False
        actual_mapping = cast(dict[str, object], actual)
        expected_mapping = cast(dict[str, object], expected)
        if actual_mapping.get("columns") != expected_mapping.get("columns"):
            return False
        actual_rows = actual_mapping.get("rows")
        expected_rows = expected_mapping.get("rows")
        if not isinstance(actual_rows, list) or not isinstance(expected_rows, list):
            return False
        if strategy == "sql_unordered":
            return sorted(map(repr, actual_rows)) == sorted(map(repr, expected_rows))
        return actual_rows == expected_rows
    return False


def trusted_compare(
    result: SandboxExecutionResult,
    expected_tests: dict[str, dict[str, object]],
) -> TrustedExecutionProjection:
    if result.status == "TIMEOUT":
        execution_status = ExecutionStatus.timeout
    elif result.status == "FAILED":
        execution_status = ExecutionStatus.failed
    else:
        execution_status = ExecutionStatus.completed

    seen: set[str] = set()
    public_results: list[dict[str, object]] = []
    hidden_total = 0
    hidden_passed = 0
    any_candidate_error = False
    for actual_test in result.tests:
        test_id = _required_string(actual_test.get("id"), label="Runner result test id")
        if test_id in seen:
            raise TrustedResultError("Runner result included a duplicate test id.")
        seen.add(test_id)
        expected = expected_tests.get(test_id)
        if expected is None:
            raise TrustedResultError("Runner result references an unknown test id.")
        if actual_test.get("visibility") != expected["visibility"]:
            raise TrustedResultError("Runner result changed a test visibility boundary.")
        error_category = _optional_string(actual_test.get("error_category"))
        passed = bool(actual_test.get("ok")) and not error_category and _compare(
            actual_test.get("actual"),
            expected.get("expected"),
            cast(dict[str, object], expected["comparison"]),
        )
        any_candidate_error = any_candidate_error or bool(error_category)
        if expected["visibility"] == "public":
            public_results.append(
                {
                    "test_id": test_id,
                    "name": test_id,
                    "passed": passed,
                    "expected": expected.get("expected"),
                    "actual": actual_test.get("actual"),
                    "error_category": error_category,
                }
            )
        else:
            hidden_total += 1
            hidden_passed += int(passed)

    if execution_status == ExecutionStatus.completed and len(seen) != len(expected_tests):
        execution_status = ExecutionStatus.failed
        any_candidate_error = True

    passed_count = sum(bool(item["passed"]) for item in public_results) + hidden_passed
    total_count = len(public_results) + hidden_total
    candidate_message = (
        "All tests passed."
        if execution_status == ExecutionStatus.completed and total_count > 0 and passed_count == total_count
        else "Execution completed. Review the failed public cases and boundary conditions."
    )
    if execution_status == ExecutionStatus.timeout:
        candidate_message = "Execution exceeded the configured time limit."
    elif execution_status == ExecutionStatus.failed and any_candidate_error:
        candidate_message = "Execution failed. Review the public error details and your implementation."
    elif execution_status == ExecutionStatus.failed:
        candidate_message = "Execution could not complete. Please retry."

    return TrustedExecutionProjection(
        execution_status=execution_status,
        runtime_ms=result.runtime_ms,
        exit_code=result.exit_code,
        error_category=result.error_category,
        public_results=public_results,
        hidden_total=hidden_total,
        hidden_passed=hidden_passed,
        stdout=result.stdout,
        stderr=result.stderr,
        candidate_message=candidate_message,
    )


def persist_terminal_result(
    connection: Connection,
    *,
    execution_id: UUID,
    projection: TrustedExecutionProjection,
) -> ExecutionStatus:
    repository = ExecutionRepository(connection)
    snapshot = repository.get(execution_id)
    if snapshot.status in TERMINAL_EXECUTION_STATUSES:
        return snapshot.status
    try:
        terminal = repository.complete(
            execution_id,
            status=projection.execution_status,
            runtime_ms=projection.runtime_ms,
            exit_code=projection.exit_code,
            error_category=projection.error_category,
        )
    except ExecutionTransitionError:
        current = repository.get(execution_id)
        if current.status in TERMINAL_EXECUTION_STATUSES:
            return current.status
        raise

    connection.execute(
        text(
            """
            INSERT INTO execution_public_results(
                execution_request_id,
                public_results,
                hidden_total,
                hidden_passed,
                stdout,
                stderr,
                candidate_message
            ) VALUES (
                :execution_id,
                CAST(:public_results AS jsonb),
                :hidden_total,
                :hidden_passed,
                :stdout,
                :stderr,
                :candidate_message
            )
            ON CONFLICT (execution_request_id) DO UPDATE SET
                public_results=EXCLUDED.public_results,
                hidden_total=EXCLUDED.hidden_total,
                hidden_passed=EXCLUDED.hidden_passed,
                stdout=EXCLUDED.stdout,
                stderr=EXCLUDED.stderr,
                candidate_message=EXCLUDED.candidate_message
            """
        ),
        {
            "execution_id": execution_id,
            "public_results": json.dumps(projection.public_results, separators=(",", ":")),
            "hidden_total": projection.hidden_total,
            "hidden_passed": projection.hidden_passed,
            "stdout": projection.stdout,
            "stderr": projection.stderr,
            "candidate_message": projection.candidate_message,
        },
    )
    return terminal
