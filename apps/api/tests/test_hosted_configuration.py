from __future__ import annotations

from pydantic import ValidationError
import pytest

from rigor_api.config import Settings


HOSTED_SETTINGS = {
    "environment": "production",
    "database_url": "postgresql+psycopg://rigor:secret@db.internal:5432/rigor",
    "operational_database_url": "postgresql+psycopg://rigor:secret@db.internal:5432/rigor",
    "valkey_url": "rediss://cache.internal:6379/0",
    "execution_adapter": "KUBERNETES_JOB",
    "sqs_execution_queue_url": "https://sqs.us-east-1.amazonaws.com/123456789012/rigor-execution",
    "local_oidc_enabled": False,
    "oidc_issuer": "https://identity.example.com",
    "oidc_jwks_url": "https://identity.example.com/.well-known/jwks.json",
    "oidc_audience": "rigor-web",
}


def hosted_settings(**overrides: object) -> Settings:
    values = {**HOSTED_SETTINGS, **overrides}
    return Settings(**values)  # type: ignore[arg-type]


def test_hosted_configuration_accepts_remote_durable_services() -> None:
    settings = hosted_settings()

    assert settings.environment == "production"
    assert settings.execution_adapter == "KUBERNETES_JOB"


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        (
            "database_url",
            "postgresql+psycopg://rigor:secret@localhost:5432/rigor",
            "non-loopback PostgreSQL",
        ),
        (
            "operational_database_url",
            "postgresql+psycopg://rigor:secret@127.0.0.1:5432/rigor",
            "non-loopback operational database",
        ),
        ("valkey_url", "redis://localhost:6379/0", "non-loopback Valkey/Redis"),
    ],
)
def test_hosted_configuration_rejects_loopback_state(
    field: str, value: str, message: str
) -> None:
    with pytest.raises(ValidationError, match=message):
        hosted_settings(**{field: value})


def test_kubernetes_execution_requires_durable_queue() -> None:
    with pytest.raises(ValidationError, match="requires an SQS execution queue"):
        hosted_settings(sqs_execution_queue_url=None)


def test_local_development_defaults_remain_supported() -> None:
    settings = Settings()

    assert settings.environment == "development"
    assert settings.execution_adapter == "LOCAL_FUNCTIONAL"
