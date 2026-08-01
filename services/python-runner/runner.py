from __future__ import annotations

import argparse
import json
import math
import os
import resource
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, cast
from uuid import UUID

MAX_SOURCE_BYTES = 100_000
MAX_TESTS = 200
MAX_STREAM_BYTES = 64 * 1024
CHILD_FILE_LIMIT_BYTES = 128 * 1024
INVOCATION_MODES = {"auto", "keyword_arguments", "positional_arguments", "single_payload", "no_arguments"}

SAFE_CHILD_ENV = {
    "HOME": "/workspace",
    "LANG": "C.UTF-8",
    "LC_ALL": "C.UTF-8",
    "PATH": "/usr/local/bin:/usr/bin:/bin",
    "PYTHONIOENCODING": "utf-8",
    "PYTHONUNBUFFERED": "1",
    "TMPDIR": "/workspace/tmp",
}

CHILD_PROGRAM = r'''
import builtins
import io
import json
import sys

MAX_CAPTURE = 65536
SAFE_MODULES = {
    "bisect",
    "collections",
    "dataclasses",
    "datetime",
    "decimal",
    "enum",
    "functools",
    "heapq",
    "inspect",
    "itertools",
    "math",
    "operator",
    "re",
    "statistics",
    "string",
    "typing",
}

class BoundedText(io.StringIO):
    def __init__(self, limit):
        super().__init__()
        self.limit = limit
        self.written = 0
        self.truncated = False

    def write(self, value):
        text = str(value)
        remaining = max(0, self.limit - self.written)
        if remaining:
            super().write(text[:remaining])
            self.written += min(len(text), remaining)
        if len(text) > remaining:
            self.truncated = True
        return len(text)

original_import = builtins.__import__

def safe_import(name, globals=None, locals=None, fromlist=(), level=0):
    root = name.split(".", 1)[0]
    if root not in SAFE_MODULES:
        raise ImportError(f"module {root!r} is not available in candidate execution")
    return original_import(name, globals, locals, fromlist, level)

safe_builtins = dict(vars(builtins))
for forbidden in ("breakpoint", "compile", "eval", "exec", "input", "open"):
    safe_builtins.pop(forbidden, None)
safe_builtins["__import__"] = safe_import

payload = json.load(sys.stdin)
captured_stdout = BoundedText(MAX_CAPTURE)
captured_stderr = BoundedText(MAX_CAPTURE)
old_stdout = sys.stdout
old_stderr = sys.stderr
protocol = {
    "ok": False,
    "actual": None,
    "error_category": None,
    "stdout": "",
    "stderr": "",
    "stdout_truncated": False,
    "stderr_truncated": False,
}

try:
    sys.stdout = captured_stdout
    sys.stderr = captured_stderr
    namespace = {"__builtins__": safe_builtins}
    exec(payload["source_code"], namespace, namespace)
    candidate = namespace.get(payload["entrypoint"])
    if not callable(candidate):
        raise TypeError("required entrypoint is not callable")
    test_input = payload.get("input")
    invocation_mode = payload.get("invocation_mode", "auto")
    if invocation_mode == "keyword_arguments" or (
        invocation_mode == "auto" and isinstance(test_input, dict)
    ):
        actual = candidate(**test_input)
    elif invocation_mode == "positional_arguments" or (
        invocation_mode == "auto" and isinstance(test_input, list)
    ):
        if not isinstance(test_input, list):
            raise TypeError("positional_arguments input must be a list")
        actual = candidate(*test_input)
    elif invocation_mode == "no_arguments":
        actual = candidate()
    else:
        actual = candidate(test_input)
    try:
        json.dumps(actual)
    except (TypeError, ValueError):
        protocol["error_category"] = "output_not_json_serializable"
    else:
        protocol["ok"] = True
        protocol["actual"] = actual
except BaseException as exc:
    protocol["error_category"] = type(exc).__name__
finally:
    sys.stdout = old_stdout
    sys.stderr = old_stderr
    protocol["stdout"] = captured_stdout.getvalue()
    protocol["stderr"] = captured_stderr.getvalue()
    protocol["stdout_truncated"] = captured_stdout.truncated
    protocol["stderr_truncated"] = captured_stderr.truncated

print("RIGOR_RESULT:" + json.dumps(protocol, separators=(",", ":"), ensure_ascii=False))
'''


class RunnerInputError(ValueError):
    pass


def parse_request(path: Path, expected_execution_id: UUID) -> dict[str, Any]:
    try:
        raw = path.read_text(encoding="utf-8")
        payload = json.loads(raw)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise RunnerInputError("Execution input is unavailable or invalid JSON.") from exc
    if not isinstance(payload, dict):
        raise RunnerInputError("Execution input must be a JSON object.")
    if payload.get("schema_version") != 1:
        raise RunnerInputError("Unsupported execution input schema version.")
    if payload.get("execution_id") != str(expected_execution_id):
        raise RunnerInputError("Execution input identifier mismatch.")

    attempt = payload.get("attempt")
    if not isinstance(attempt, int) or isinstance(attempt, bool) or attempt < 1:
        raise RunnerInputError("Execution attempt is missing or invalid.")

    source = payload.get("source_code")
    if not isinstance(source, str) or not source:
        raise RunnerInputError("Candidate source is required.")
    if len(source.encode("utf-8")) > MAX_SOURCE_BYTES:
        raise RunnerInputError("Candidate source exceeds the execution limit.")

    entrypoint = payload.get("entrypoint", "solve")
    if not isinstance(entrypoint, str) or not entrypoint.isidentifier():
        raise RunnerInputError("Candidate entrypoint is invalid.")

    invocation_mode = payload.get("invocation_mode", "auto")
    if invocation_mode not in INVOCATION_MODES:
        raise RunnerInputError("Candidate invocation mode is invalid.")

    tests = payload.get("tests")
    if not isinstance(tests, list) or not tests:
        raise RunnerInputError("At least one test input is required.")
    if len(tests) > MAX_TESTS:
        raise RunnerInputError("Execution contains too many test inputs.")

    normalized_tests: list[dict[str, Any]] = []
    seen_test_ids: set[str] = set()
    for index, item in enumerate(tests):
        if not isinstance(item, dict):
            raise RunnerInputError("Each test input must be an object.")
        test_id = item.get("id")
        visibility = item.get("visibility", "hidden")
        if not isinstance(test_id, str) or not test_id:
            raise RunnerInputError(f"Test input {index} has no identifier.")
        if test_id in seen_test_ids:
            raise RunnerInputError(f"Duplicate test identifier {test_id!r}.")
        seen_test_ids.add(test_id)
        if visibility not in {"public", "hidden"}:
            raise RunnerInputError(f"Test input {test_id} has invalid visibility.")
        if "expected_output" in item or "expected" in item:
            raise RunnerInputError("Expected outputs must never enter the candidate sandbox.")
        normalized_tests.append(
            {
                "id": test_id,
                "visibility": visibility,
                "input": item.get("input"),
            }
        )

    return {
        "attempt": attempt,
        "source_code": source,
        "entrypoint": entrypoint,
        "invocation_mode": invocation_mode,
        "tests": normalized_tests,
    }


def _apply_child_limits(timeout_seconds: int) -> None:
    cpu_soft = max(1, math.ceil(timeout_seconds))
    cpu_hard = cpu_soft + 1
    resource.setrlimit(resource.RLIMIT_CPU, (cpu_soft, cpu_hard))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    resource.setrlimit(
        resource.RLIMIT_FSIZE,
        (CHILD_FILE_LIMIT_BYTES, CHILD_FILE_LIMIT_BYTES),
    )
    resource.setrlimit(resource.RLIMIT_NOFILE, (32, 32))
    if hasattr(resource, "RLIMIT_NPROC"):
        resource.setrlimit(resource.RLIMIT_NPROC, (32, 32))


def _read_bounded(path: Path) -> str:
    try:
        with path.open("rb") as stream:
            return stream.read(MAX_STREAM_BYTES).decode("utf-8", errors="replace")
    except OSError:
        return ""


def _parse_child_protocol(stdout_path: Path) -> dict[str, Any] | None:
    content = _read_bounded(stdout_path)
    for line in reversed(content.splitlines()):
        if not line.startswith("RIGOR_RESULT:"):
            continue
        try:
            value = json.loads(line.removeprefix("RIGOR_RESULT:"))
        except json.JSONDecodeError:
            return None
        return value if isinstance(value, dict) else None
    return None


def _workspace() -> Path:
    configured = Path("/workspace")
    if configured.exists() and os.access(configured, os.W_OK):
        return configured
    fallback = Path(tempfile.gettempdir()) / "rigor-runner-workspace"
    fallback.mkdir(parents=True, exist_ok=True)
    return fallback


def _terminate_process_group(process: subprocess.Popen[str]) -> None:
    if process.poll() is not None:
        return
    try:
        if os.name == "posix":
            os.killpg(process.pid, signal.SIGKILL)
        else:
            process.kill()
    except ProcessLookupError:
        return


def execute_test(
    *,
    source_code: str,
    entrypoint: str,
    invocation_mode: str,
    test_input: object,
    timeout_seconds: int,
) -> tuple[dict[str, Any], str, str, int]:
    workspace = _workspace()
    temp_root = workspace / "tmp"
    temp_root.mkdir(parents=True, exist_ok=True)

    with tempfile.NamedTemporaryFile(dir=temp_root, delete=True) as stdout_file:
        with tempfile.NamedTemporaryFile(dir=temp_root, delete=True) as stderr_file:
            process = subprocess.Popen(
                [sys.executable, "-I", "-S", "-c", CHILD_PROGRAM],
                stdin=subprocess.PIPE,
                stdout=stdout_file,
                stderr=stderr_file,
                text=True,
                cwd=workspace,
                env=SAFE_CHILD_ENV,
                preexec_fn=lambda: _apply_child_limits(timeout_seconds),
                start_new_session=True,
            )
            child_input = json.dumps(
                {
                    "source_code": source_code,
                    "entrypoint": entrypoint,
                    "invocation_mode": invocation_mode,
                    "input": test_input,
                },
                separators=(",", ":"),
                ensure_ascii=False,
            )
            try:
                process.communicate(child_input, timeout=timeout_seconds)
            except subprocess.TimeoutExpired:
                _terminate_process_group(process)
                process.wait(timeout=2)
                return (
                    {
                        "ok": False,
                        "actual": None,
                        "error_category": "timeout",
                        "stdout": "",
                        "stderr": "",
                        "stdout_truncated": False,
                        "stderr_truncated": False,
                    },
                    "",
                    "",
                    process.returncode or 124,
                )

            stdout_file.flush()
            stderr_file.flush()
            stdout_path = Path(stdout_file.name)
            stderr_path = Path(stderr_file.name)
            protocol = _parse_child_protocol(stdout_path)
            raw_stderr = _read_bounded(stderr_path)
            if protocol is None:
                protocol = {
                    "ok": False,
                    "actual": None,
                    "error_category": "runner_protocol_error",
                    "stdout": "",
                    "stderr": "",
                    "stdout_truncated": False,
                    "stderr_truncated": False,
                }
            return protocol, _read_bounded(stdout_path), raw_stderr, process.returncode or 0


def run_request(
    request: dict[str, Any],
    *,
    timeout_seconds: int,
) -> dict[str, Any]:
    started = time.monotonic()
    source_code = str(request["source_code"])
    entrypoint = str(request["entrypoint"])
    invocation_mode = str(request["invocation_mode"])
    tests = cast(list[dict[str, object]], request["tests"])
    deadline = started + timeout_seconds

    results: list[dict[str, object]] = []
    public_stdout_parts: list[str] = []
    public_stderr_parts: list[str] = []
    terminal_status = "COMPLETED"
    last_exit_code = 0

    for item in tests:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            terminal_status = "TIMEOUT"
            break
        per_test_timeout = max(1, min(math.ceil(remaining), timeout_seconds))
        protocol, _raw_stdout, raw_stderr, exit_code = execute_test(
            source_code=source_code,
            entrypoint=entrypoint,
            invocation_mode=invocation_mode,
            test_input=item.get("input"),
            timeout_seconds=per_test_timeout,
        )
        last_exit_code = exit_code
        visibility = str(item["visibility"])
        error_category = protocol.get("error_category")
        if error_category == "timeout":
            terminal_status = "TIMEOUT"

        results.append(
            {
                "id": str(item["id"]),
                "visibility": visibility,
                "ok": bool(protocol.get("ok")),
                "actual": protocol.get("actual"),
                "error_category": str(error_category) if error_category else None,
            }
        )

        if visibility == "public":
            public_stdout_parts.append(str(protocol.get("stdout", "")))
            public_stderr_parts.append(str(protocol.get("stderr", "")))
            if raw_stderr:
                public_stderr_parts.append(raw_stderr)

        if terminal_status == "TIMEOUT":
            break

    runtime_ms = round((time.monotonic() - started) * 1000)
    public_stdout = "".join(public_stdout_parts)[:MAX_STREAM_BYTES]
    public_stderr = "".join(public_stderr_parts)[:MAX_STREAM_BYTES]
    return {
        "schema_version": 1,
        "attempt": int(request["attempt"]),
        "status": terminal_status,
        "runtime_ms": runtime_ms,
        "exit_code": last_exit_code,
        "tests": results,
        "stdout": public_stdout,
        "stderr": public_stderr,
        "stdout_truncated": sum(map(len, public_stdout_parts)) > MAX_STREAM_BYTES,
        "stderr_truncated": sum(map(len, public_stderr_parts)) > MAX_STREAM_BYTES,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Rigor isolated Python execution runner")
    parser.add_argument("--execution-id", required=True)
    parser.add_argument("--input", required=True)
    parser.add_argument("--timeout-seconds", type=int, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    attempt = 0
    try:
        execution_id = UUID(args.execution_id)
        if args.timeout_seconds < 1 or args.timeout_seconds > 30:
            raise RunnerInputError("Execution timeout is outside the server policy.")
        request = parse_request(Path(args.input), execution_id)
        attempt = int(request["attempt"])
        result = run_request(request, timeout_seconds=args.timeout_seconds)
    except (RunnerInputError, ValueError) as exc:
        result = {
            "schema_version": 1,
            "attempt": attempt,
            "status": "FAILED",
            "runtime_ms": 0,
            "exit_code": 2,
            "tests": [],
            "stdout": "",
            "stderr": "",
            "error_category": exc.__class__.__name__,
        }

    result["execution_id"] = str(args.execution_id)
    print(
        "RIGOR_EXECUTION_RESULT:"
        + json.dumps(result, separators=(",", ":"), ensure_ascii=False),
        flush=True,
    )
    return 0 if result.get("status") == "COMPLETED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
