from __future__ import annotations

import json
from typing import Any

from rigor_api.execution import (
    LOCAL_FUNCTIONAL,
    ExecutionLimits,
    KubernetesJobAdapter,
    LocalFunctionalPythonRunner,
)
from rigor_api.schemas import SubmissionRuntime


def test_local_python_runner_projects_public_and_hidden_results_safely() -> None:
    tests: list[dict[str, Any]] = [
        {
            "id": "public-1",
            "name": "doubles a value",
            "visibility": "public",
            "input": 4,
            "expected_output": 8,
        },
        {
            "id": "hidden-secret-case",
            "name": "private",
            "visibility": "hidden",
            "input": "HIDDEN_INPUT_DO_NOT_LEAK",
            "expected_output": "HIDDEN_EXPECTED_DO_NOT_LEAK",
        },
    ]

    result = LocalFunctionalPythonRunner().execute(
        SubmissionRuntime.python,
        "def solve(payload):\n    return payload * 2\n",
        tests,
    )

    assert LocalFunctionalPythonRunner.adapter_name == LOCAL_FUNCTIONAL
    assert result.status == "failed"
    assert len(result.public_results) == 1
    assert result.public_results[0].passed is True
    assert result.hidden_summary.total == 1
    assert result.hidden_summary.passed == 0
    candidate_payload = json.dumps(
        {
            "status": result.status,
            "public": [item.model_dump(mode="json") for item in result.public_results],
            "hidden": result.hidden_summary.model_dump(mode="json"),
            "message": result.candidate_message,
        }
    )
    assert "HIDDEN_INPUT_DO_NOT_LEAK" not in candidate_payload
    assert "HIDDEN_EXPECTED_DO_NOT_LEAK" not in candidate_payload
    assert "hidden-secret-case" not in candidate_payload


def test_local_python_runner_enforces_wall_clock_timeout() -> None:
    result = LocalFunctionalPythonRunner().execute(
        SubmissionRuntime.python,
        "def solve(payload):\n    while True:\n        pass\n",
        [
            {
                "id": "public-timeout",
                "name": "terminates",
                "visibility": "public",
                "input": 1,
                "expected_output": 1,
            }
        ],
        limits=ExecutionLimits(timeout_ms=100, cpu_seconds=1),
    )

    assert result.status == "error"
    assert result.error_category == "timeout"
    assert result.public_results == []
    assert result.candidate_message is not None
    assert "time limit" in result.candidate_message


def test_local_python_runner_returns_deterministic_quality_signals() -> None:
    result = LocalFunctionalPythonRunner().execute(
        SubmissionRuntime.python,
        "def solve(payload: int) -> int:\n    return payload + 1\n",
        [
            {
                "id": "public-pass",
                "name": "increments",
                "visibility": "public",
                "input": 1,
                "expected_output": 2,
            }
        ],
    )

    assert result.status == "passed"
    assert result.error_category is None
    assert result.quality_signals["syntax_valid"] is True
    assert result.quality_signals["function_count"] == 1
    assert result.quality_signals["public_passed"] == 1
    assert result.quality_signals["public_total"] == 1


class FakeKubernetesClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def create_namespaced_job(self, namespace: str, body: dict[str, Any]) -> object:
        self.calls.append((namespace, body))
        return {"accepted": True}


def test_kubernetes_contract_enforces_production_sandbox_controls() -> None:
    client = FakeKubernetesClient()
    adapter = KubernetesJobAdapter(client=client)
    limits = ExecutionLimits(timeout_ms=2_500, memory_mb=192, process_count=8)

    response = adapter.submit("abc123", "source-abc123", limits)
    manifest = client.calls[0][1]
    pod_spec = manifest["spec"]["template"]["spec"]
    container = pod_spec["containers"][0]

    assert response == {"accepted": True}
    assert client.calls[0][0] == "rigor-execution"
    assert pod_spec["runtimeClassName"] == "gvisor"
    assert pod_spec["automountServiceAccountToken"] is False
    assert pod_spec["securityContext"]["runAsNonRoot"] is True
    assert container["securityContext"]["readOnlyRootFilesystem"] is True
    assert container["securityContext"]["capabilities"]["drop"] == ["ALL"]
    assert manifest["spec"]["activeDeadlineSeconds"] == 3
    assert manifest["spec"]["ttlSecondsAfterFinished"] == 60
    assert adapter.deny_all_network_policy("abc123")["spec"]["egress"] == []

