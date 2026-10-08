from __future__ import annotations

import pytest
from fastapi import HTTPException

from rigor_api import execution_plane
from rigor_api.config import Settings


def hosted_settings(adapter: str) -> Settings:
    return Settings(
        environment="production",
        database_url="postgresql+psycopg://rigor:secret@db.internal:5432/rigor",
        operational_database_url=(
            "postgresql+psycopg://rigor:secret@db.internal:5432/rigor"
        ),
        valkey_url="rediss://cache.internal:6379/0",
        execution_adapter=adapter,
        sqs_execution_queue_url=(
            "https://sqs.us-east-1.amazonaws.com/123456789012/rigor-execution"
            if adapter == execution_plane.KUBERNETES_JOB
            else None
        ),
        local_oidc_enabled=False,
        oidc_issuer="https://identity.example.com",
        oidc_jwks_url="https://identity.example.com/.well-known/jwks.json",
        oidc_audience="rigor-web",
    )


def test_vercel_execution_plane_fails_before_enqueue_without_credentials(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        execution_plane,
        "get_settings",
        lambda: hosted_settings(execution_plane.VERCEL_SANDBOX),
    )
    monkeypatch.delenv("VERCEL_OIDC_TOKEN", raising=False)
    monkeypatch.delenv("VERCEL_TOKEN", raising=False)
    monkeypatch.delenv("VERCEL_PROJECT_ID", raising=False)
    monkeypatch.delenv("RIGOR_VERCEL_PROJECT_ID", raising=False)

    with pytest.raises(HTTPException) as captured:
        execution_plane.require_candidate_execution_plane()

    assert captured.value.status_code == 503
    assert captured.value.detail == "Candidate execution is temporarily unavailable."


def test_vercel_execution_plane_accepts_project_scoped_credentials(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        execution_plane,
        "get_settings",
        lambda: hosted_settings(execution_plane.VERCEL_SANDBOX),
    )
    monkeypatch.setenv("VERCEL_OIDC_TOKEN", "test-oidc-token")
    monkeypatch.setenv("VERCEL_PROJECT_ID", "prj_test")

    assert execution_plane.require_candidate_execution_plane() == execution_plane.VERCEL_SANDBOX


def test_kubernetes_execution_plane_does_not_require_vercel_credentials(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        execution_plane,
        "get_settings",
        lambda: hosted_settings(execution_plane.KUBERNETES_JOB),
    )
    monkeypatch.delenv("VERCEL_OIDC_TOKEN", raising=False)
    monkeypatch.delenv("VERCEL_PROJECT_ID", raising=False)

    assert execution_plane.require_candidate_execution_plane() == execution_plane.KUBERNETES_JOB
