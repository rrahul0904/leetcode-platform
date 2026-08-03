from __future__ import annotations

from concurrent.futures import Future
from urllib import request
from uuid import uuid4

import pytest
from rigor_api import local_execution_controller as local_controller
from rigor_api.execution_kubernetes import SandboxHandle


def _handle():
    execution_id = uuid4()
    return SandboxHandle(
        execution_id=execution_id,
        namespace="local-docker",
        job_name=f"local-{execution_id}",
        input_secret_name=f"input-local-{execution_id}",
        network_policy_name=f"deny-local-{execution_id}",
    )


def _python_payload() -> dict[str, object]:
    return {
        "schema_version": 1,
        "execution_id": str(uuid4()),
        "attempt": 1,
        "source_code": "def solve(value): return value",
        "entrypoint": "solve",
        "tests": [{"id": "public-1", "visibility": "public", "input": 1}],
    }


def test_new_controller_observes_pre_restart_execution_as_missing() -> None:
    executor = local_controller.LocalHttpSandboxExecutor(
        python_url="http://python-runner:8081",
        sql_url="http://sql-runner:8082",
        maximum_parallel=1,
    )
    try:
        observation = executor.observe(_handle())
        assert observation.state == "MISSING"
    finally:
        executor.close()


def test_cleanup_forgets_running_future_and_requests_cancellation() -> None:
    executor = local_controller.LocalHttpSandboxExecutor(
        python_url="http://python-runner:8081",
        sql_url="http://sql-runner:8082",
        maximum_parallel=1,
    )
    handle = _handle()
    future: Future[dict[str, object]] = Future()
    executor._futures[handle.execution_id] = future
    executor._attempts[handle.execution_id] = 1
    try:
        executor.cleanup(handle)
        assert future.cancelled()
        assert executor.observe(handle).state == "MISSING"
    finally:
        executor.close()


def test_runner_transport_outage_is_classified_for_durable_retry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def unavailable(*args: object, **kwargs: object):
        del args, kwargs
        raise OSError("runner unavailable")

    monkeypatch.setattr(request, "urlopen", unavailable)

    with pytest.raises(
        local_controller.LocalExecutionTransportError,
        match="transport failed",
    ):
        local_controller.LocalHttpSandboxExecutor._invoke(
            "http://python-runner:8081",
            _python_payload(),
            10,
        )


def test_local_runner_urls_fail_closed_for_non_http_boundaries() -> None:
    with pytest.raises(
        local_controller.LocalExecutionTransportError,
        match="internal HTTP Docker network",
    ):
        local_controller.LocalHttpSandboxExecutor._invoke(
            "https://public.example/python",
            _python_payload(),
            10,
        )
