from __future__ import annotations

import json
from typing import Any
from uuid import uuid4

import pytest

from rigor_api.vercel_sandbox_execution import SandboxSession, VercelSandboxError
from rigor_api.vercel_sandbox_runtime import (
    PACKAGE_BOOTSTRAP_DOMAINS,
    HardenedVercelSandboxClient,
)


def test_checked_command_accepts_zero_exit_code_json() -> None:
    raw = json.dumps({"command": {"exitCode": "0"}}).encode()
    assert HardenedVercelSandboxClient._command_exit_code(raw) == 0


def test_checked_command_accepts_final_exit_code_from_ndjson() -> None:
    raw = b'\n'.join(
        [
            json.dumps({"command": {"id": "cmd_1"}}).encode(),
            json.dumps({"command": {"id": "cmd_1", "exitCode": 7}}).encode(),
        ]
    )
    assert HardenedVercelSandboxClient._command_exit_code(raw) == 7


def test_checked_command_rejects_missing_terminal_status() -> None:
    with pytest.raises(VercelSandboxError, match="terminal exit code"):
        HardenedVercelSandboxClient._command_exit_code(
            json.dumps({"command": {"id": "cmd_1"}}).encode()
        )


def test_execute_rejects_nonzero_sandbox_command(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_request(
        self: HardenedVercelSandboxClient,
        path: str,
        *,
        method: str = "GET",
        body: bytes | None = None,
        content_type: str = "application/json",
        headers: dict[str, str] | None = None,
        timeout: float = 30.0,
    ) -> bytes:
        del self, path, method, body, content_type, headers, timeout
        return json.dumps({"command": {"exitCode": 12}}).encode()

    monkeypatch.setattr(HardenedVercelSandboxClient, "_request", fake_request)
    client = HardenedVercelSandboxClient(
        token="token",
        project_id="prj_skillforge",
    )

    with pytest.raises(VercelSandboxError, match="exit code 12"):
        client.execute(
            SandboxSession(session_id="sbx_1", name="skillforge-test"),
            command="python",
            args=["runner.py"],
            timeout_ms=5_000,
        )


def test_sql_bootstrap_sandbox_uses_bounded_package_egress(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    def fake_json_request(
        self: HardenedVercelSandboxClient,
        path: str,
        *,
        method: str = "GET",
        payload: dict[str, object] | None = None,
        timeout: float = 30.0,
    ) -> dict[str, object]:
        del self, timeout
        captured.update(path=path, method=method, payload=payload)
        return {"session": {"id": "sbx_sql"}}

    monkeypatch.setattr(
        HardenedVercelSandboxClient,
        "_json_request",
        fake_json_request,
    )
    client = HardenedVercelSandboxClient(
        token="token",
        project_id="prj_skillforge",
    )

    session = client.create(
        execution_id=uuid4(),
        runtime="python3.13",
        timeout_ms=180_000,
        allow_package_bootstrap=True,
    )

    assert session.session_id == "sbx_sql"
    payload = captured["payload"]
    assert isinstance(payload, dict)
    assert payload["persistent"] is False
    policy = payload["networkPolicy"]
    assert isinstance(policy, dict)
    assert policy == {
        "mode": "custom",
        "allowedDomains": PACKAGE_BOOTSTRAP_DOMAINS,
        "allowedCIDRs": [],
        "deniedCIDRs": [],
    }
    assert "cdn.amazonlinux.com" in PACKAGE_BOOTSTRAP_DOMAINS
    assert "pypi.org" in PACKAGE_BOOTSTRAP_DOMAINS
    assert "files.pythonhosted.org" in PACKAGE_BOOTSTRAP_DOMAINS
