from __future__ import annotations

import ast
import json
import math
import os
import signal
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from .schemas import HiddenTestSummary, PublicTestResult, SubmissionRuntime

LOCAL_FUNCTIONAL = "LOCAL_FUNCTIONAL"


@dataclass(frozen=True)
class ExecutionLimits:
    timeout_ms: int = 3_000
    output_bytes: int = 64 * 1024
    memory_mb: int = 256
    file_bytes: int = 2 * 1024 * 1024
    process_count: int = 16
    cpu_seconds: int = 2


@dataclass(frozen=True)
class ExecutionResult:
    status: str
    public_results: list[PublicTestResult]
    hidden_summary: HiddenTestSummary
    error_category: str | None
    duration_ms: int
    candidate_message: str | None = None
    quality_signals: dict[str, object] = field(default_factory=dict)
    memory_kb: int | None = None


class ExecutionAdapter(Protocol):
    """Runtime boundary. Implementations must never expose hidden test inputs."""

    adapter_name: str

    def execute(
        self,
        runtime: SubmissionRuntime,
        source: str,
        tests: list[dict[str, Any]],
        *,
        limits: ExecutionLimits | None = None,
        challenge: dict[str, Any] | None = None,
    ) -> ExecutionResult: ...


def source_quality_signals(source: str) -> dict[str, object]:
    signals: dict[str, object] = {
        "line_count": len(source.splitlines()),
        "contains_todo": "TODO" in source.upper() or "..." in source,
        "debug_print_count": source.count("print("),
    }
    try:
        tree = ast.parse(source)
    except SyntaxError:
        signals["syntax_valid"] = False
        return signals
    signals.update(
        {
            "syntax_valid": True,
            "function_count": sum(isinstance(node, ast.FunctionDef) for node in ast.walk(tree)),
            "class_count": sum(isinstance(node, ast.ClassDef) for node in ast.walk(tree)),
            "loop_count": sum(isinstance(node, (ast.For, ast.While)) for node in ast.walk(tree)),
        }
    )
    return signals


def _entrypoint(source: str) -> str | None:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return None
    functions = [node.name for node in tree.body if isinstance(node, ast.FunctionDef)]
    if "solve" in functions:
        return "solve"
    return functions[0] if functions else None


def _resource_limiter(limits: ExecutionLimits) -> Any:
    def apply_limits() -> None:
        try:
            import resource

            cpu = max(1, limits.cpu_seconds)
            resource.setrlimit(resource.RLIMIT_CPU, (cpu, cpu))
            memory = limits.memory_mb * 1024 * 1024
            resource.setrlimit(resource.RLIMIT_AS, (memory, memory))
            resource.setrlimit(resource.RLIMIT_FSIZE, (limits.file_bytes, limits.file_bytes))
            resource.setrlimit(resource.RLIMIT_NOFILE, (32, 32))
            if hasattr(resource, "RLIMIT_NPROC"):
                resource.setrlimit(
                    resource.RLIMIT_NPROC, (limits.process_count, limits.process_count)
                )
        except (ImportError, OSError, ValueError):
            # The adapter reports which limits are requested. Platforms without a
            # particular rlimit still retain timeout/process-group/output controls.
            pass

    return apply_limits


class LocalFunctionalPythonRunner:
    """Functional local runner, explicitly not a production security sandbox."""

    adapter_name = LOCAL_FUNCTIONAL

    _HARNESS = r'''
import builtins
import contextlib
import inspect
import io
import json
import sys

class LimitedText(io.StringIO):
    def __init__(self, limit):
        super().__init__()
        self.limit = limit
        self.used = 0
    def write(self, value):
        self.used += len(value.encode("utf-8", errors="replace"))
        if self.used > self.limit:
            raise RuntimeError("candidate output limit exceeded")
        return super().write(value)

allowed_imports = {
    "bisect", "collections", "dataclasses", "datetime", "decimal", "enum",
    "functools", "heapq", "inspect", "itertools", "math", "operator", "re",
    "statistics", "string", "typing"
}
real_import = builtins.__import__
real_compile = builtins.compile
real_exec = builtins.exec
def controlled_import(name, globals=None, locals=None, fromlist=(), level=0):
    if name.split(".")[0] not in allowed_imports:
        raise ImportError("that module is unavailable in the local functional runner")
    return real_import(name, globals, locals, fromlist, level)

safe_builtins = dict(vars(builtins))
for blocked in ("open", "eval", "exec", "compile", "input", "breakpoint"):
    safe_builtins.pop(blocked, None)
safe_builtins["__import__"] = controlled_import
namespace = {"__builtins__": safe_builtins, "__name__": "candidate_submission"}
payload = json.load(sys.stdin)

def invoke(function, value):
    if payload["entrypoint"] == "solve":
        return function(value)
    if not isinstance(value, dict):
        return function(value)
    parameters = inspect.signature(function).parameters
    kwargs = {}
    aliases = {"max_rows_per_batch": "capacity", "max_capacity": "capacity"}
    for name in parameters:
        source_name = name if name in value else aliases.get(name)
        if source_name is None or source_name not in value:
            raise TypeError("test input does not provide the required function arguments")
        kwargs[name] = value[source_name]
    return function(**kwargs)

try:
    sink = LimitedText(payload["candidate_output_bytes"])
    with contextlib.redirect_stdout(sink), contextlib.redirect_stderr(sink):
        code = real_compile(payload["source"], "submission.py", "exec")
        real_exec(code, namespace)
    function = namespace.get(payload["entrypoint"])
    if not callable(function):
        raise TypeError("submission must define the starter function")
    results = []
    for test in payload["tests"]:
        try:
            with contextlib.redirect_stdout(sink), contextlib.redirect_stderr(sink):
                actual = invoke(function, test.get("input"))
            expected_exception = test.get("expected_output") == "ValueError"
            results.append({
                "id": test["id"],
                "passed": False if expected_exception else actual == test.get("expected_output"),
                "actual": actual,
            })
        except Exception as exc:
            expected_exception = test.get("expected_output")
            results.append({
                "id": test["id"],
                "passed": expected_exception == type(exc).__name__,
                "error": type(exc).__name__,
            })
    print(json.dumps({"results": results}, default=str, separators=(",", ":")))
except Exception as exc:
    print(json.dumps({"fatal_error": type(exc).__name__}, separators=(",", ":")))
'''

    def execute(
        self,
        runtime: SubmissionRuntime,
        source: str,
        tests: list[dict[str, Any]],
        *,
        limits: ExecutionLimits | None = None,
        challenge: dict[str, Any] | None = None,
    ) -> ExecutionResult:
        selected_limits = limits or ExecutionLimits()
        started = time.monotonic()
        if runtime != SubmissionRuntime.python:
            return self._error(started, tests, "unsupported_runtime")
        entrypoint = _entrypoint(source)
        if entrypoint is None:
            return self._error(
                started,
                tests,
                "syntax_or_entrypoint_error",
                "Define the function shown in the starter code before running tests.",
                source,
            )
        payload = json.dumps(
            {
                "source": source,
                "tests": tests,
                "entrypoint": entrypoint,
                "candidate_output_bytes": selected_limits.output_bytes // 2,
            }
        )
        process: subprocess.Popen[str] | None = None
        try:
            with tempfile.TemporaryDirectory(prefix="rigor-local-functional-") as directory:
                process = subprocess.Popen(
                    [sys.executable, "-I", "-S", "-c", self._HARNESS],
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    cwd=Path(directory),
                    env={"LANG": "C.UTF-8", "LC_ALL": "C.UTF-8", "PYTHONHASHSEED": "0"},
                    text=True,
                    start_new_session=True,
                    preexec_fn=_resource_limiter(selected_limits) if os.name == "posix" else None,
                )
                try:
                    stdout, _ = process.communicate(
                        payload, timeout=selected_limits.timeout_ms / 1000
                    )
                except subprocess.TimeoutExpired:
                    self._terminate_group(process)
                    process.communicate()
                    return self._error(
                        started,
                        tests,
                        "timeout",
                        "Execution exceeded the question time limit.",
                        source,
                    )
        finally:
            if process is not None and process.poll() is None:
                self._terminate_group(process)
                process.wait(timeout=1)
        if len(stdout.encode("utf-8", errors="replace")) > selected_limits.output_bytes:
            return self._error(started, tests, "output_limit", source=source)
        if process.returncode != 0:
            category = "resource_limit" if process.returncode < 0 else "runner_error"
            return self._error(started, tests, category, source=source)
        try:
            response = json.loads(stdout.strip())
        except (json.JSONDecodeError, UnboundLocalError):
            return self._error(started, tests, "runner_protocol_error", source=source)
        if "fatal_error" in response:
            return self._error(
                started,
                tests,
                str(response["fatal_error"]),
                "The submission could not be initialized. Check syntax and the starter function.",
                source,
            )
        duration = round((time.monotonic() - started) * 1000)
        return project_results(tests, response["results"], duration, source)

    @staticmethod
    def _terminate_group(process: subprocess.Popen[str]) -> None:
        try:
            if os.name == "posix":
                os.killpg(process.pid, signal.SIGKILL)
            else:
                process.kill()
        except ProcessLookupError:
            pass

    @staticmethod
    def _error(
        started: float,
        tests: list[dict[str, Any]],
        category: str,
        message: str | None = None,
        source: str = "",
    ) -> ExecutionResult:
        return ExecutionResult(
            status="error",
            public_results=[],
            hidden_summary=HiddenTestSummary(
                total=sum(test.get("visibility") != "public" for test in tests), passed=0
            ),
            error_category=category,
            duration_ms=round((time.monotonic() - started) * 1000),
            candidate_message=message or "Execution could not complete within the configured limits.",
            quality_signals=source_quality_signals(source),
        )


def project_results(
    tests: list[dict[str, Any]],
    raw_results: list[dict[str, Any]],
    duration_ms: int,
    source: str,
) -> ExecutionResult:
    by_id = {str(result["id"]): result for result in raw_results}
    public: list[PublicTestResult] = []
    hidden_total = 0
    hidden_passed = 0
    any_failed = False
    runtime_error = False
    for test in tests:
        raw = by_id.get(str(test["id"]), {"passed": False, "error": "missing_result"})
        passed = bool(raw.get("passed"))
        any_failed = any_failed or not passed
        runtime_error = runtime_error or ("error" in raw and not passed)
        if test.get("visibility") == "public":
            public.append(
                PublicTestResult(
                    id=str(test["id"]),
                    name=str(test.get("name", test["id"])),
                    passed=passed,
                    expected_output=test.get("expected_output"),
                    actual_output=raw.get("actual"),
                )
            )
        else:
            hidden_total += 1
            hidden_passed += int(passed)
    quality = source_quality_signals(source)
    quality["public_passed"] = sum(result.passed for result in public)
    quality["public_total"] = len(public)
    return ExecutionResult(
        status="failed" if any_failed else "passed",
        public_results=public,
        hidden_summary=HiddenTestSummary(total=hidden_total, passed=hidden_passed),
        error_category="runtime_error" if runtime_error else None,
        duration_ms=duration_ms,
        candidate_message=(
            "All tests passed."
            if not any_failed
            else "Review the failed public cases and test boundary conditions."
        ),
        quality_signals=quality,
    )


class KubernetesClient(Protocol):
    def create_namespaced_job(self, namespace: str, body: dict[str, Any]) -> object: ...


@dataclass(frozen=True)
class KubernetesJobAdapter:
    """Production adapter contract; execution result polling is controller-owned."""

    client: KubernetesClient
    namespace: str = "rigor-execution"
    runtime_class_name: str = "gvisor"
    image: str = "rigor-python-runner:production"
    adapter_name: str = "KUBERNETES_JOB"

    def job_manifest(
        self, request_id: str, source_secret_name: str, limits: ExecutionLimits
    ) -> dict[str, Any]:
        deadline = max(1, math.ceil(limits.timeout_ms / 1000))
        labels = {"app.kubernetes.io/name": "rigor-runner", "rigor/request-id": request_id}
        return {
            "apiVersion": "batch/v1",
            "kind": "Job",
            "metadata": {"name": f"run-{request_id}", "labels": labels},
            "spec": {
                "activeDeadlineSeconds": deadline,
                "backoffLimit": 0,
                "ttlSecondsAfterFinished": 60,
                "template": {
                    "metadata": {"labels": labels},
                    "spec": {
                        "runtimeClassName": self.runtime_class_name,
                        "restartPolicy": "Never",
                        "automountServiceAccountToken": False,
                        "securityContext": {
                            "runAsNonRoot": True,
                            "runAsUser": 65532,
                            "runAsGroup": 65532,
                            "seccompProfile": {"type": "RuntimeDefault"},
                        },
                        "containers": [
                            {
                                "name": "runner",
                                "image": self.image,
                                "args": ["--request-id", request_id],
                                "securityContext": {
                                    "allowPrivilegeEscalation": False,
                                    "readOnlyRootFilesystem": True,
                                    "capabilities": {"drop": ["ALL"]},
                                },
                                "resources": {
                                    "requests": {"cpu": "100m", "memory": "64Mi"},
                                    "limits": {
                                        "cpu": "1",
                                        "memory": f"{limits.memory_mb}Mi",
                                        "ephemeral-storage": f"{max(8, limits.file_bytes // 1048576)}Mi",
                                    },
                                },
                                "volumeMounts": [
                                    {"name": "workspace", "mountPath": "/workspace"},
                                    {
                                        "name": "source",
                                        "mountPath": "/run/rigor-source",
                                        "readOnly": True,
                                    },
                                ],
                            }
                        ],
                        "volumes": [
                            {"name": "workspace", "emptyDir": {"sizeLimit": "16Mi"}},
                            {
                                "name": "source",
                                "secret": {"secretName": source_secret_name, "defaultMode": 256},
                            },
                        ],
                    },
                },
            },
        }

    def submit(self, request_id: str, source_secret_name: str, limits: ExecutionLimits) -> object:
        return self.client.create_namespaced_job(
            self.namespace, self.job_manifest(request_id, source_secret_name, limits)
        )

    @staticmethod
    def deny_all_network_policy(request_id: str) -> dict[str, Any]:
        return {
            "apiVersion": "networking.k8s.io/v1",
            "kind": "NetworkPolicy",
            "metadata": {"name": f"deny-run-{request_id}"},
            "spec": {
                "podSelector": {"matchLabels": {"rigor/request-id": request_id}},
                "policyTypes": ["Ingress", "Egress"],
                "ingress": [],
                "egress": [],
            },
        }
