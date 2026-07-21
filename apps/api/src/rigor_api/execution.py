from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol, cast

from sqlalchemy import Engine

from .schemas import HiddenTestSummary, PublicTestResult, SubmissionRuntime


@dataclass(frozen=True)
class ExecutionResult:
    status: str
    public_results: list[PublicTestResult]
    hidden_summary: HiddenTestSummary
    error_category: str | None
    duration_ms: int


class ExecutionAdapter(Protocol):
    """Runtime-independent boundary implemented by local and future cluster runners."""

    def execute(
        self,
        runtime: SubmissionRuntime,
        source: str,
        tests: list[dict[str, Any]],
    ) -> ExecutionResult: ...


class LocalControlledRunner:
    """Functional development runner; it is explicitly not a production security sandbox."""

    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    def execute(
        self,
        runtime: SubmissionRuntime,
        source: str,
        tests: list[dict[str, Any]],
    ) -> ExecutionResult:
        if runtime == SubmissionRuntime.python:
            return self._execute_python(source, tests)
        return self._execute_sql(source, tests)

    def _execute_python(self, source: str, tests: list[dict[str, Any]]) -> ExecutionResult:
        started = time.monotonic()
        harness = r"""
import builtins
import contextlib
import io
import json
import sys

allowed_imports = {
    "bisect", "collections", "dataclasses", "datetime", "decimal", "enum",
    "functools", "heapq", "itertools", "math", "operator", "re", "statistics", "typing"
}
real_import = builtins.__import__
real_compile = builtins.compile
real_exec = builtins.exec
def controlled_import(name, globals=None, locals=None, fromlist=(), level=0):
    if name.split(".")[0] not in allowed_imports:
        raise ImportError(f"module {name!r} is unavailable in the local controlled runner")
    return real_import(name, globals, locals, fromlist, level)

safe_builtins = dict(vars(builtins))
for blocked in ("open", "eval", "exec", "compile", "input", "breakpoint"):
    safe_builtins.pop(blocked, None)
safe_builtins["__import__"] = controlled_import
namespace = {"__builtins__": safe_builtins, "__name__": "candidate_submission"}
payload = json.load(sys.stdin)
try:
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        code = real_compile(payload["source"], "submission.py", "exec")
        real_exec(code, namespace)
    solve = namespace.get("solve")
    if not callable(solve):
        raise TypeError("submission must define solve(payload)")
    results = []
    for test in payload["tests"]:
        try:
            with (
                contextlib.redirect_stdout(io.StringIO()),
                contextlib.redirect_stderr(io.StringIO()),
            ):
                actual = solve(test.get("input"))
            passed = actual == test.get("expected_output")
            results.append({"id": test["id"], "passed": passed, "actual": actual})
        except Exception as exc:
            results.append({
                "id": test["id"], "passed": False,
                "error": type(exc).__name__
            })
    print(json.dumps({"results": results}, default=str))
except Exception as exc:
    print(json.dumps({"fatal_error": type(exc).__name__, "message": str(exc)}))
"""
        try:
            with tempfile.TemporaryDirectory(prefix="rigor-local-runner-") as directory:
                process = subprocess.run(
                    [sys.executable, "-I", "-S", "-c", harness],
                    input=json.dumps({"source": source, "tests": tests}),
                    cwd=Path(directory),
                    env={"PATH": os.environ.get("PATH", "")},
                    capture_output=True,
                    text=True,
                    timeout=3,
                    check=False,
                )
        except subprocess.TimeoutExpired:
            return self._runner_error(started, tests, "timeout")
        duration = round((time.monotonic() - started) * 1000)
        if process.returncode != 0:
            return self._runner_error(started, tests, "runner_error")
        try:
            payload = json.loads(process.stdout.strip())
        except json.JSONDecodeError:
            return self._runner_error(started, tests, "runner_protocol_error")
        if "fatal_error" in payload:
            return ExecutionResult(
                status="error",
                public_results=[],
                hidden_summary=HiddenTestSummary(
                    total=sum(test.get("visibility") != "public" for test in tests), passed=0
                ),
                error_category=str(payload["fatal_error"]),
                duration_ms=duration,
            )
        return self._project_results(tests, payload["results"], duration)

    def _execute_sql(self, source: str, tests: list[dict[str, Any]]) -> ExecutionResult:
        started = time.monotonic()
        normalized = source.strip().rstrip(";").strip()
        lowered = normalized.casefold()
        if not (lowered.startswith("select ") or lowered.startswith("with ")):
            return self._runner_error(started, tests, "sql_read_only_required")
        forbidden = ("public.", "pg_catalog", "information_schema", "copy ", "dblink")
        if any(value in lowered for value in forbidden) or ";" in normalized:
            return self._runner_error(started, tests, "sql_statement_rejected")
        raw_results: list[dict[str, Any]] = []
        try:
            for test in tests:
                test_input: object = test.get("input")
                if not isinstance(test_input, dict):
                    raise ValueError("SQL tests require an input object")
                typed_input = cast(dict[str, object], test_input)
                setup_value: object = typed_input.get("setup_sql", [])
                if not isinstance(setup_value, list):
                    raise ValueError("SQL setup_sql must be a list of statements")
                setup_objects = cast(list[object], setup_value)
                if not all(isinstance(value, str) for value in setup_objects):
                    raise ValueError("SQL setup_sql must be a list of statements")
                setup = cast(list[str], setup_objects)
                with self.engine.connect() as connection:
                    transaction = connection.begin()
                    try:
                        connection.exec_driver_sql("SET LOCAL statement_timeout = '2000ms'")
                        connection.exec_driver_sql("SET LOCAL search_path = pg_temp")
                        for statement in setup:
                            connection.exec_driver_sql(statement)
                        rows = connection.exec_driver_sql(normalized).fetchall()
                        actual = [list(row) for row in rows]
                    finally:
                        transaction.rollback()
                raw_results.append(
                    {
                        "id": test["id"],
                        "passed": actual == test.get("expected_output"),
                        "actual": actual,
                    }
                )
        except Exception as exc:
            return self._runner_error(started, tests, type(exc).__name__)
        duration = round((time.monotonic() - started) * 1000)
        return self._project_results(tests, raw_results, duration)

    @staticmethod
    def _project_results(
        tests: list[dict[str, Any]], raw_results: list[dict[str, Any]], duration: int
    ) -> ExecutionResult:
        result_by_id = {str(result["id"]): result for result in raw_results}
        public: list[PublicTestResult] = []
        hidden_total = 0
        hidden_passed = 0
        any_failed = False
        any_runtime_error = False
        for test in tests:
            result = result_by_id.get(str(test["id"]), {"passed": False, "error": "missing"})
            passed = bool(result.get("passed"))
            any_failed = any_failed or not passed
            any_runtime_error = any_runtime_error or "error" in result
            if test.get("visibility") == "public":
                public.append(
                    PublicTestResult(
                        id=str(test["id"]),
                        name=str(test.get("name", test["id"])),
                        passed=passed,
                        expected_output=test.get("expected_output"),
                        actual_output=result.get("actual"),
                    )
                )
            else:
                hidden_total += 1
                hidden_passed += int(passed)
        return ExecutionResult(
            status="failed" if any_failed else "passed",
            public_results=public,
            hidden_summary=HiddenTestSummary(total=hidden_total, passed=hidden_passed),
            error_category="runtime_error" if any_runtime_error else None,
            duration_ms=duration,
        )

    @staticmethod
    def _runner_error(
        started: float, tests: list[dict[str, Any]], category: str
    ) -> ExecutionResult:
        return ExecutionResult(
            status="error",
            public_results=[],
            hidden_summary=HiddenTestSummary(
                total=sum(test.get("visibility") != "public" for test in tests), passed=0
            ),
            error_category=category,
            duration_ms=round((time.monotonic() - started) * 1000),
        )
