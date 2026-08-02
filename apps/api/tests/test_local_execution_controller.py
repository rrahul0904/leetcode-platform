from __future__ import annotations

import json
import time
from uuid import uuid4

import pytest

from rigor_api import local_execution_controller as local_controller
from rigor_api.execution_results import RESULT_PREFIX


def test_local_queue_rejects_invalid_or_oversized_messages() -> None:
    with pytest.raises(local_controller.LocalExecutionTransportError, match="invalid"):
        local_controller.LocalExecutionQueueClient._validate_body("")
    with pytest.raises(local_controller.LocalExecutionTransportError, match="valid JSON"):
        local_controller.LocalExecutionQueueClient._validate_body("not-json")
    with pytest.raises(local_controller.LocalExecutionTransportError, match="JSON object"):
        local_controller.LocalExecutionQueueClient._validate_body("[]")


def test_local_http_executor_projects_runner_result(monkeypatch: pytest.MonkeyPatch) -> None:
    execution_id = uuid4()

    def fake_invoke(
        url: str,
        payload: dict[str, object],
        timeout_seconds: int,
    ) -> dict[str, object]:
        del url, timeout_seconds
        return {
            "schema_version": 1,
            "execution_id": payload["execution_id"],
            "attempt": payload["attempt"],
            "status": "COMPLETED",
            "runtime_ms": 3,
            "exit_code": 0,
            "tests": [
                {
                    "id": "public-1",
                    "visibility": "public",
                    "ok": True,
                    "actual": 42,
                    "error_category": None,
                }
            ],
            "stdout": "",
            "stderr": "",
            "error_category": None,
        }

    monkeypatch.setattr(
        local_controller.LocalHttpSandboxExecutor,
        "_invoke",
        staticmethod(fake_invoke),
    )
    executor = local_controller.LocalHttpSandboxExecutor(
        python_url="http://python-runner:8081",
        sql_url="http://sql-runner:8082",
        maximum_parallel=1,
    )
    try:
        handle = executor.create_python_execution(
            execution_id=execution_id,
            request_payload={
                "schema_version": 1,
                "execution_id": str(execution_id),
                "attempt": 1,
                "source_code": "def solve(value): return value",
                "entrypoint": "solve",
                "tests": [
                    {"id": "public-1", "visibility": "public", "input": 42}
                ],
            },
            profile_name="python-small",
        )
        observation = executor.observe(handle)
        for _ in range(50):
            if observation.state != "RUNNING":
                break
            time.sleep(0.01)
            observation = executor.observe(handle)

        assert observation.state == "SUCCEEDED"
        assert observation.logs is not None
        assert observation.logs.startswith(RESULT_PREFIX)
        payload = json.loads(observation.logs.removeprefix(RESULT_PREFIX))
        assert payload["execution_id"] == str(execution_id)
        assert payload["tests"][0]["actual"] == 42
    finally:
        executor.close()


def test_local_http_executor_reports_runner_health(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_ready(url: str) -> bool:
        return url.endswith("8081")

    monkeypatch.setattr(
        local_controller.LocalHttpSandboxExecutor,
        "_runner_ready",
        staticmethod(fake_ready),
    )
    executor = local_controller.LocalHttpSandboxExecutor(
        python_url="http://python-runner:8081",
        sql_url="http://sql-runner:8082",
    )
    try:
        assert executor.health() == (True, False)
    finally:
        executor.close()
