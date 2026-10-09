from __future__ import annotations

import pytest
from pydantic import ValidationError

from rigor_api.config import Settings


@pytest.mark.parametrize("adapter", ["LOCAL_FUNCTIONAL", "LOCAL_DOCKER"])
def test_local_execution_is_allowed_only_for_local_development(adapter: str) -> None:
    settings = Settings(environment="development", execution_adapter=adapter)

    assert settings.execution_adapter == adapter


@pytest.mark.parametrize("environment", ["staging", "production"])
@pytest.mark.parametrize("adapter", ["LOCAL_FUNCTIONAL", "LOCAL_DOCKER"])
def test_local_execution_is_rejected_for_deployable_environments(
    environment: str,
    adapter: str,
) -> None:
    with pytest.raises(ValidationError, match=f"{adapter} candidate execution is forbidden"):
        Settings(environment=environment, execution_adapter=adapter)


def test_isolated_execution_configuration_is_accepted_for_production() -> None:
    settings = Settings(
        environment="production",
        database_url="postgresql+psycopg://rigor:secret@db.internal:5432/rigor",
        operational_database_url="postgresql+psycopg://rigor:secret@db.internal:5432/rigor",
        valkey_url="rediss://cache.internal:6379/0",
        execution_adapter="KUBERNETES_JOB",
        sqs_execution_queue_url=(
            "https://sqs.us-east-1.amazonaws.com/123456789012/rigor-execution"
        ),
        local_oidc_enabled=False,
        oidc_issuer="https://identity.example.com",
        oidc_jwks_url="https://identity.example.com/.well-known/jwks.json",
    )

    assert settings.execution_adapter == "KUBERNETES_JOB"


@pytest.mark.parametrize("environment", ["staging", "production"])
def test_local_oidc_is_rejected_for_deployable_environments(environment: str) -> None:
    with pytest.raises(ValidationError, match="Local OIDC authentication is forbidden"):
        Settings(
            environment=environment,
            execution_adapter="KUBERNETES_JOB",
            oidc_issuer="https://identity.example.com",
            oidc_jwks_url="https://identity.example.com/.well-known/jwks.json",
        )
