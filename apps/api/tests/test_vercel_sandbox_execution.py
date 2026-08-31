from __future__ import annotations

import io
import tarfile
from typing import Any
from uuid import uuid4

import pytest

from rigor_api.vercel_sandbox_execution import (
    SandboxSession,
    VercelSandboxClient,
    VercelSandboxError,
    vercel_sandbox_enabled,
)


def test_vercel_sandbox_enabled_is_explicit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("RIGOR_EXECUTION_ADAPTER", raising=False)
    assert vercel_sandbox_enabled() is False

    monkeypatch.setenv("RIGOR_EXECUTION_ADAPTER", "vercel_sandbox")
    assert vercel_sandbox_enabled() is True


def test_discover_requires_sandbox_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in (
        "VERCEL_OIDC_TOKEN",
        "VERCEL_TOKEN",
        "VERCEL_PROJECT_ID",
        "RIGOR_VERCEL_PROJECT_ID",
        "VERCEL_TEAM_ID",
    ):
        monkeypatch.delenv(key, raising=False)

    with pytest.raises(VercelSandboxError, match="authentication is unavailable"):
        VercelSandboxClient.discover()

    monkeypatch.setenv("VERCEL_OIDC_TOKEN", "oidc-token")
    with pytest.raises(VercelSandboxError, match="project scope is unavailable"):
        VercelSandboxClient.discover()


def test_discover_uses_vercel_deployment_scope(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VERCEL_OIDC_TOKEN", "oidc-token")
    monkeypatch.setenv("VERCEL_PROJECT_ID", "prj_skillforge")
    monkeypatch.setenv("VERCEL_TEAM_ID", "team_skillforge")

    client = VercelSandboxClient.discover()

    assert client.token == "oidc-token"
    assert client.project_id == "prj_skillforge"
    assert client.team_id == "team_skillforge"


def test_python_sandbox_is_nonpersistent_and_deny_all(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    def fake_json_request(
        self: VercelSandboxClient,
        path: str,
        *,
        method: str = "GET",
        payload: dict[str, object] | None = None,
        timeout: float = 30.0,
    ) -> dict[str, object]:
        del self, timeout
        captured.update(path=path, method=method, payload=payload)
        return {"session": {"id": "sbx_python"}}

    monkeypatch.setattr(VercelSandboxClient, "_json_request", fake_json_request)
    client = VercelSandboxClient(token="token", project_id="prj_skillforge")

    session = client.create(
        execution_id=uuid4(),
        runtime="python3.13",
        timeout_ms=60_000,
    )

    assert session.session_id == "sbx_python"
    assert captured["path"] == "/v2/sandboxes"
    assert captured["method"] == "POST"
    payload = captured["payload"]
    assert isinstance(payload, dict)
    assert payload["projectId"] == "prj_skillforge"
    assert payload["runtime"] == "python3.13"
    assert payload["persistent"] is False
    assert payload["networkPolicy"] == {"mode": "deny-all"}


def test_sql_bootstrap_has_bounded_egress_only_for_package_install(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    def fake_json_request(
        self: VercelSandboxClient,
        path: str,
        *,
        method: str = "GET",
        payload: dict[str, object] | None = None,
        timeout: float = 30.0,
    ) -> dict[str, object]:
        del self, timeout
        captured.update(path=path, method=method, payload=payload)
        return {"session": {"id": "sbx_sql"}}

    monkeypatch.setattr(VercelSandboxClient, "_json_request", fake_json_request)
    client = VercelSandboxClient(token="token", project_id="prj_skillforge")

    client.create(
        execution_id=uuid4(),
        runtime="python3.13",
        timeout_ms=180_000,
        allow_package_bootstrap=True,
    )

    payload = captured["payload"]
    assert isinstance(payload, dict)
    policy = payload["networkPolicy"]
    assert isinstance(policy, dict)
    assert policy["mode"] == "custom"
    assert set(policy["allowedDomains"]) == {
        "deb.debian.org",
        "security.debian.org",
        "archive.ubuntu.com",
        "security.ubuntu.com",
        "ports.ubuntu.com",
    }
    assert policy["allowedCIDRs"] == []


def test_network_policy_can_be_closed_before_candidate_execution(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    def fake_json_request(
        self: VercelSandboxClient,
        path: str,
        *,
        method: str = "GET",
        payload: dict[str, object] | None = None,
        timeout: float = 30.0,
    ) -> dict[str, object]:
        del self, timeout
        captured.update(path=path, method=method, payload=payload)
        return {"session": {"id": "sbx_sql"}}

    monkeypatch.setattr(VercelSandboxClient, "_json_request", fake_json_request)
    client = VercelSandboxClient(token="token", project_id="prj_skillforge")
    session = SandboxSession(session_id="sbx_sql", name="skillforge-test")

    client.update_network_policy(session, "deny-all")

    assert captured == {
        "path": "/v2/sandboxes/sessions/sbx_sql/network-policy",
        "method": "POST",
        "payload": {"mode": "deny-all"},
    }


def test_uploaded_sandbox_files_are_private_and_bounded_to_requested_files(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    def fake_request(
        self: VercelSandboxClient,
        path: str,
        *,
        method: str = "GET",
        body: bytes | None = None,
        content_type: str = "application/json",
        headers: dict[str, str] | None = None,
        timeout: float = 30.0,
    ) -> bytes:
        del self, timeout
        captured.update(
            path=path,
            method=method,
            body=body,
            content_type=content_type,
            headers=headers,
        )
        return b"{}"

    monkeypatch.setattr(VercelSandboxClient, "_request", fake_request)
    client = VercelSandboxClient(token="token", project_id="prj_skillforge")
    session = SandboxSession(session_id="sbx_python", name="skillforge-test")

    client.upload_files(
        session,
        {
            "runner.py": b"print('runner')\n",
            "input.json": b'{"candidate":true}',
        },
    )

    assert captured["path"] == "/v2/sandboxes/sessions/sbx_python/fs/write"
    assert captured["method"] == "POST"
    assert captured["content_type"] == "application/gzip"
    assert captured["headers"] == {"x-cwd": "/home/vercel-sandbox"}
    body = captured["body"]
    assert isinstance(body, bytes)

    with tarfile.open(fileobj=io.BytesIO(body), mode="r:gz") as archive:
        members = archive.getmembers()
        assert {member.name for member in members} == {"runner.py", "input.json"}
        assert all(member.mode == 0o600 for member in members)
