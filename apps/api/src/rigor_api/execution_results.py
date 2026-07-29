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
    return {
        "schema_version": 1,
        "execution_id": str(package.execution_id),
        "attempt": package.attempt_count,
        "source_code": package.source_code,
        "entrypoint": str(package.input_payload.get("entrypoint") or "solve"),
        "tests": sanitized_tests,
    }


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


def _comparison_policy(item: dict[str, object]) -> dict[str, object]:
    raw = item.get("comparison")
    if raw is None:
        return {"strategy": "exact"}
    if isinstance(raw, str):
        policy: dict[str, object] = {"strategy": raw}
    elif isinstance(raw, dict):
        policy = cast(dict[str, object], raw)
    else:
        raise TrustedResultError("Question comparison policy is invalid.")
    strategy = str(policy.get("strategy") or "exact")
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
    mode = _object_dict(structured.get("mode_specification"), label="Question execution mode")
    tests = _object_list(mode.get("tests"), label="Question expected tests")
    if not tests or len(tests) > MAX_RESULT_TESTS:
        raise TrustedResultError("Question expected test set is empty or too large.")

    expected: dict[str, dict[str, object]] = {}
    for index, raw_item in enumerate(tests):
        item = _object_dict(raw_item, label="Question expected test")
        test_id_value = item.get("id")
        test_id = (
            test_id_value
            if isinstance(test_id_value, str) and test_id_value
            else f"test-{index + 1}"
        )
        if test_id in expected:
            raise TrustedResultError("Question expected test identifiers must be unique.")
        name_value = item.get("name")
        visibility_value = item.get("visibility")
        expected[test_id] = {
            "id": test_id,
            "name": name_value if isinstance(name_value, str) and name_value else test_id,
            "visibility": (
                visibility_value
                if isinstance(visibility_value, str) and visibility_value in {"public", "hidden"}
                else "hidden"
            ),
            "expected_output": item.get("expected_output"),
            "comparison": _comparison_policy(item),
        }
    return expected


def _canonical_json(value: object) -> str:
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    except (TypeError, ValueError) as exc:
        raise TrustedResultError("Comparison value is not JSON serializable.") from exc


def _compare_value(actual: object, expected: object, policy: dict[str, object]) -> bool:
    strategy = str(policy.get("strategy") or "exact")
    if strategy in {"exact", "json"}:
        return actual == expected
    if strategy == "normalized_text":
        return " ".join(str(actual).split()) == " ".join(str(expected).split())
    if strategy == "numeric_tolerance":
        tolerance_raw = policy.get("tolerance", 1e-9)
        if not isinstance(tolerance_raw, (int, float)) or isinstance(tolerance_raw, bool):
            raise TrustedResultError("Numeric comparison tolerance must be numeric.")
        tolerance = float(tolerance_raw)
        if not math.isfinite(tolerance) or tolerance < 0:
            raise TrustedResultError("Numeric comparison tolerance is invalid.")
        if not isinstance(actual, (int, float)) or isinstance(actual, bool):
            return False
        if not isinstance(expected, (int, float)) or isinstance(expected, bool):
            return False
        return math.isclose(float(actual), float(expected), rel_tol=0.0, abs_tol=tolerance)
    if strategy == "unordered":
        if not isinstance(actual, list) or not isinstance(expected, list):
            return False
        return sorted(_canonical_json(item) for item in actual) == sorted(
            _canonical_json(item) for item in expected
        )
    raise TrustedResultError(f"Unsupported trusted comparison strategy {strategy!r}.")


def _test_passed(actual: dict[str, object], expected: dict[str, object]) -> bool:
    expected_output = expected.get("expected_output")
    error_category = actual.get("error_category")
    if isinstance(expected_output, str) and expected_output.endswith("Error"):
        return error_category == expected_output
    if not bool(actual.get("ok")):
        return False
    policy_value = expected.get("comparison")
    policy = _object_dict(policy_value, label="Trusted comparison policy")
    return _compare_value(actual.get("actual"), expected_output, policy)


def trusted_compare(
    sandbox: SandboxExecutionResult,
    expected_tests: dict[str, dict[str, object]],
) -> TrustedExecutionProjection:
    if sandbox.status == "TIMEOUT":
        terminal = ExecutionStatus.timeout
    elif sandbox.status == "FAILED":
        terminal = ExecutionStatus.failed
    else:
        terminal = ExecutionStatus.completed

    returned_ids = {str(item["id"]) for item in sandbox.tests}
    unknown_ids = returned_ids.difference(expected_tests)
    if unknown_ids:
        raise TrustedResultError("Runner returned unknown test identifiers.")
    if terminal is ExecutionStatus.completed and returned_ids != set(expected_tests):
        raise TrustedResultError("Completed runner result omitted one or more expected tests.")

    public_results: list[dict[str, object]] = []
    hidden_total = sum(
        1 for item in expected_tests.values() if str(item.get("visibility") or "hidden") == "hidden"
    )
    hidden_passed = 0
    for actual in sandbox.tests:
        test_id = str(actual["id"])
        expected = expected_tests[test_id]
        expected_visibility = str(expected.get("visibility") or "hidden")
        if actual["visibility"] != expected_visibility:
            raise TrustedResultError(f"Runner changed visibility for test {test_id!r}.")
        passed = _test_passed(actual, expected)
        if expected_visibility == "public":
            public_results.append(
                {
                    "test_id": test_id,
                    "name": str(expected.get("name") or test_id),
                    "passed": passed,
                    "expected": expected.get("expected_output"),
                    "actual": actual.get("actual"),
                    "error_category": actual.get("error_category"),
                }
            )
        else:
            hidden_passed += int(passed)

    if terminal is ExecutionStatus.completed:
        passed_count = sum(bool(item["passed"]) for item in public_results) + hidden_passed
        total_count = len(public_results) + hidden_total
        if total_count and passed_count == total_count:
            message = "All evaluated tests passed."
        elif total_count:
            message = f"{passed_count} of {total_count} evaluated tests passed."
        else:
            message = "Execution completed."
    elif terminal is ExecutionStatus.timeout:
        message = "Execution exceeded the configured time limit."
    else:
        message = "Execution failed inside the isolated runner."

    return TrustedExecutionProjection(
        execution_status=terminal,
        runtime_ms=sandbox.runtime_ms,
        exit_code=sandbox.exit_code,
        error_category=sandbox.error_category,
        public_results=public_results,
        hidden_total=hidden_total,
        hidden_passed=hidden_passed,
        stdout=sandbox.stdout,
        stderr=sandbox.stderr,
        candidate_message=message,
    )


def persist_terminal_result(
    connection: Connection,
    *,
    execution_id: UUID,
    projection: TrustedExecutionProjection,
) -> ExecutionStatus:
    repository = ExecutionRepository(connection)
    current = repository.get(execution_id)
    if current.status in TERMINAL_EXECUTION_STATUSES:
        return current.status
    try:
        repository.transition(
            execution_id,
            projection.execution_status,
            details={
                "runtime_ms": projection.runtime_ms,
                "error_category": projection.error_category or "",
            },
        )
    except ExecutionTransitionError:
        current = repository.get(execution_id)
        if current.status in TERMINAL_EXECUTION_STATUSES:
            return current.status
        raise

    connection.execute(
        text(
            """
            UPDATE execution_requests
            SET runtime_ms=:runtime_ms,
                exit_code=:exit_code,
                error_category=:error_category,
                result_reference=:result_reference,
                lease_owner=NULL,
                lease_expires_at=NULL
            WHERE id=:execution_id
            """
        ),
        {
            "execution_id": execution_id,
            "runtime_ms": projection.runtime_ms,
            "exit_code": projection.exit_code,
            "error_category": projection.error_category,
            "result_reference": f"db://execution-public-results/{execution_id}",
        },
    )
    connection.execute(
        text(
            """
            INSERT INTO execution_public_results (
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
            ON CONFLICT (execution_request_id) DO UPDATE
            SET public_results=EXCLUDED.public_results,
                hidden_total=EXCLUDED.hidden_total,
                hidden_passed=EXCLUDED.hidden_passed,
                stdout=EXCLUDED.stdout,
                stderr=EXCLUDED.stderr,
                candidate_message=EXCLUDED.candidate_message,
                updated_at=CURRENT_TIMESTAMP
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
    return projection.execution_status
