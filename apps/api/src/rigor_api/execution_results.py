from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, cast
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


@dataclass(frozen=True)
class SandboxExecutionResult:
    execution_id: UUID
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
        input_payload=(dict(row["input_payload"]) if isinstance(row["input_payload"], dict) else {}),
        limits=dict(row["limits"]) if isinstance(row["limits"], dict) else {},
        trace_id=str(row["trace_id"]),
    )


def sandbox_request(package: DispatchPackage) -> dict[str, object]:
    payload = dict(package.input_payload)
    tests = payload.get("tests")
    if not isinstance(tests, list):
        raise TrustedResultError("Execution input has no test list.")
    for item in tests:
        if not isinstance(item, dict):
            raise TrustedResultError("Execution test input is invalid.")
        if "expected_output" in item or "expected" in item:
            raise TrustedResultError("Expected answers must not enter the candidate sandbox.")
    return {
        "schema_version": 1,
        "execution_id": str(package.execution_id),
        "source_code": package.source_code,
        "entrypoint": str(payload.get("entrypoint") or "solve"),
        "tests": tests,
    }


def parse_runner_result(log_text: str, *, execution_id: UUID) -> SandboxExecutionResult:
    encoded = log_text.encode("utf-8", errors="replace")
    if len(encoded) > MAX_RESULT_LOG_BYTES:
        raise TrustedResultError("Runner result log exceeds the trusted transport limit.")

    payload: dict[str, Any] | None = None
    for line in reversed(log_text.splitlines()):
        if not line.startswith(RESULT_PREFIX):
            continue
        try:
            value = json.loads(line.removeprefix(RESULT_PREFIX))
        except json.JSONDecodeError as exc:
            raise TrustedResultError("Runner emitted malformed result JSON.") from exc
        if isinstance(value, dict):
            payload = cast(dict[str, Any], value)
        break
    if payload is None:
        raise TrustedResultError("Runner result marker was not found.")
    if payload.get("schema_version") != 1:
        raise TrustedResultError("Unsupported runner result schema version.")
    if payload.get("execution_id") != str(execution_id):
        raise TrustedResultError("Runner result execution identifier mismatch.")

    status = str(payload.get("status") or "")
    if status not in {"COMPLETED", "FAILED", "TIMEOUT"}:
        raise TrustedResultError("Runner emitted an unsupported terminal status.")
    raw_tests = payload.get("tests")
    if not isinstance(raw_tests, list) or len(raw_tests) > MAX_RESULT_TESTS:
        raise TrustedResultError("Runner test result list is invalid.")
    tests: list[dict[str, object]] = []
    seen: set[str] = set()
    for item in raw_tests:
        if not isinstance(item, dict):
            raise TrustedResultError("Runner test result is invalid.")
        test_id = str(item.get("id") or "")
        visibility = str(item.get("visibility") or "")
        if not test_id or test_id in seen:
            raise TrustedResultError("Runner test identifiers must be unique and non-empty.")
        if visibility not in {"public", "hidden"}:
            raise TrustedResultError("Runner test visibility is invalid.")
        seen.add(test_id)
        tests.append(
            {
                "id": test_id,
                "visibility": visibility,
                "ok": bool(item.get("ok")),
                "actual": item.get("actual"),
                "error_category": (
                    str(item["error_category"]) if item.get("error_category") else None
                ),
            }
        )

    runtime_ms = payload.get("runtime_ms")
    exit_code = payload.get("exit_code")
    if not isinstance(runtime_ms, int) or runtime_ms < 0:
        raise TrustedResultError("Runner runtime is invalid.")
    if not isinstance(exit_code, int):
        raise TrustedResultError("Runner exit code is invalid.")
    stdout = str(payload.get("stdout") or "")[:MAX_PUBLIC_STREAM_BYTES]
    stderr = str(payload.get("stderr") or "")[:MAX_PUBLIC_STREAM_BYTES]
    return SandboxExecutionResult(
        execution_id=execution_id,
        status=status,
        runtime_ms=runtime_ms,
        exit_code=exit_code,
        tests=tests,
        stdout=stdout,
        stderr=stderr,
        error_category=(str(payload["error_category"]) if payload.get("error_category") else None),
    )


def load_expected_tests(
    connection: Connection,
    *,
    question_version_id: UUID,
) -> dict[str, dict[str, object]]:
    structured = connection.execute(
        text("SELECT structured_content FROM question_versions WHERE id=:id"),
        {"id": question_version_id},
    ).scalar_one_or_none()
    if not isinstance(structured, dict):
        raise TrustedResultError("Question execution specification is unavailable.")
    mode = structured.get("mode_specification")
    if not isinstance(mode, dict):
        raise TrustedResultError("Question execution mode is unavailable.")
    tests = mode.get("tests")
    if not isinstance(tests, list):
        raise TrustedResultError("Question expected tests are unavailable.")
    expected: dict[str, dict[str, object]] = {}
    for index, item in enumerate(tests):
        if not isinstance(item, dict):
            continue
        test_id = str(item.get("id") or f"test-{index + 1}")
        expected[test_id] = {
            "id": test_id,
            "name": str(item.get("name") or test_id),
            "visibility": str(item.get("visibility") or "hidden"),
            "expected_output": item.get("expected_output"),
        }
    return expected


def _test_passed(actual: dict[str, object], expected_output: object) -> bool:
    error_category = actual.get("error_category")
    if isinstance(expected_output, str) and expected_output.endswith("Error"):
        return error_category == expected_output
    return bool(actual.get("ok")) and actual.get("actual") == expected_output


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

    public_results: list[dict[str, object]] = []
    hidden_total = 0
    hidden_passed = 0
    for actual in sandbox.tests:
        test_id = str(actual["id"])
        expected = expected_tests.get(test_id)
        if expected is None:
            raise TrustedResultError(f"Runner returned unknown test {test_id!r}.")
        expected_visibility = str(expected.get("visibility") or "hidden")
        if actual["visibility"] != expected_visibility:
            raise TrustedResultError(f"Runner changed visibility for test {test_id!r}.")
        passed = _test_passed(actual, expected.get("expected_output"))
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
            hidden_total += 1
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
