"""The employer execution switch stays closed without reviewed cloud wiring."""

from __future__ import annotations

import pytest
import rigor_api.employer_code_execution_routes as routes
from rigor_api.config import Settings


def test_employer_execution_is_disabled_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(routes, "get_settings", lambda: Settings())
    assert routes.employer_execution_enabled() is False


def test_hosted_execution_needs_switch_queue_and_isolated_adapter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = Settings(
        environment="production",
        local_oidc_enabled=False,
        oidc_issuer="https://issuer.example.com",
        oidc_jwks_url="https://issuer.example.com/jwks",
        execution_adapter="KUBERNETES_JOB",
        employer_code_execution_enabled=True,
    )
    monkeypatch.setattr(routes, "get_settings", lambda: settings)
    assert routes.employer_execution_enabled() is False
    settings.employer_execution_queue_url = "https://sqs.us-east-1.amazonaws.com/123456789012/employer"
    assert routes.employer_execution_enabled() is True
    settings.execution_adapter = "UNISOLATED"
    assert routes.employer_execution_enabled() is False
