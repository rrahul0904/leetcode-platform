from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Self
from urllib.parse import urlsplit

from pydantic import AliasChoices, Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def default_content_root() -> Path:
    candidate = Path.cwd() / "content"
    if candidate.exists():
        return candidate
    for parent in Path(__file__).resolve().parents:
        candidate = parent / "content"
        if candidate.exists():
            return candidate
    return Path.cwd() / "content"


def _is_loopback_service_url(value: str) -> bool:
    """Return True when a service URL resolves to a loopback-only host.

    Hosted Rigor environments must never silently fall back to the local
    development PostgreSQL/Valkey defaults when a secret or environment
    variable is missing.
    """

    host = urlsplit(value).hostname
    return host is None or host.lower() in {"localhost", "127.0.0.1", "::1"}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="RIGOR_",
        env_file=".env",
        extra="ignore",
        populate_by_name=True,
    )

    environment: str = "development"
    database_url: str = "postgresql+psycopg://rigor:rigor_local_only@localhost:5434/rigor"
    operational_database_url: str | None = None
    valkey_url: str = "redis://localhost:6381/0"
    execution_adapter: str = "LOCAL_FUNCTIONAL"
    ai_adapter: str = "DETERMINISTIC"
    tutor_model: str = "gpt-5.2"
    arena_generation_limit_per_hour: int = Field(
        default=30,
        ge=1,
        le=10_000,
        validation_alias=AliasChoices(
            "RIGOR_ARENA_GENERATION_LIMIT_PER_HOUR",
            "ARENA_GENERATION_LIMIT_PER_HOUR",
        ),
    )
    openai_api_key: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices("RIGOR_OPENAI_API_KEY", "OPENAI_API_KEY"),
    )
    content_root: Path = Field(default_factory=default_content_root)
    allowed_origins: list[str] = ["http://localhost:3001"]
    oidc_issuer: str = "http://localhost:8002/local-oidc"
    oidc_audience: str = "rigor-web"
    oidc_jwks_url: str | None = None
    local_oidc_enabled: bool = True
    local_oidc_redirect_uris: list[str] = ["http://localhost:3001/auth/callback"]

    clerk_issuer: str | None = Field(
        default=None,
        validation_alias=AliasChoices("RIGOR_CLERK_ISSUER", "CLERK_ISSUER"),
    )
    clerk_jwks_url: str | None = Field(
        default=None,
        validation_alias=AliasChoices("RIGOR_CLERK_JWKS_URL", "CLERK_JWKS_URL"),
    )
    clerk_webhook_secret: str | None = Field(
        default=None,
        validation_alias=AliasChoices("RIGOR_CLERK_WEBHOOK_SECRET", "CLERK_WEBHOOK_SECRET"),
    )
    jwt_audience: str | None = Field(
        default=None,
        validation_alias=AliasChoices("RIGOR_JWT_AUDIENCE", "JWT_AUDIENCE"),
    )
    aws_region: str = Field(
        default="us-east-1",
        validation_alias=AliasChoices("RIGOR_AWS_REGION", "AWS_REGION"),
    )
    sqs_execution_queue_url: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "RIGOR_SQS_EXECUTION_QUEUE_URL", "SQS_EXECUTION_QUEUE_URL"
        ),
    )
    s3_upload_bucket: str | None = Field(
        default=None,
        validation_alias=AliasChoices("RIGOR_S3_UPLOAD_BUCKET", "S3_UPLOAD_BUCKET"),
    )
    s3_export_bucket: str | None = Field(
        default=None,
        validation_alias=AliasChoices("RIGOR_S3_EXPORT_BUCKET", "S3_EXPORT_BUCKET"),
    )
    sentry_dsn: str | None = Field(
        default=None,
        validation_alias=AliasChoices("RIGOR_SENTRY_DSN", "SENTRY_DSN"),
    )

    @model_validator(mode="after")
    def normalize_identity_provider(self) -> Self:
        if self.clerk_issuer:
            self.oidc_issuer = self.clerk_issuer.rstrip("/")
        if self.clerk_jwks_url:
            self.oidc_jwks_url = self.clerk_jwks_url
        if self.jwt_audience:
            self.oidc_audience = self.jwt_audience
        return self

    @model_validator(mode="after")
    def production_execution_must_fail_closed(self) -> Self:
        environment = self.environment.strip().lower()
        adapter = self.execution_adapter.strip().upper()
        hosted_environment = environment in {"production", "staging"}
        hosted_adapters = {"KUBERNETES_JOB", "VERCEL_SANDBOX"}
        local_adapters = {"LOCAL_FUNCTIONAL", "LOCAL_DOCKER"}

        if hosted_environment and adapter in local_adapters:
            raise ValueError(
                f"{adapter} candidate execution is forbidden in staging and production."
            )
        if hosted_environment and adapter not in hosted_adapters:
            raise ValueError(
                f"{adapter or 'EMPTY'} candidate execution is not an approved hosted adapter. "
                "Configure KUBERNETES_JOB or VERCEL_SANDBOX explicitly."
            )
        if hosted_environment and self.local_oidc_enabled:
            raise ValueError(
                "Local OIDC authentication is forbidden in staging and production. "
                "Configure the production identity provider instead."
            )
        if (
            hosted_environment
            and not self.local_oidc_enabled
            and (not self.oidc_jwks_url or not self.oidc_issuer)
        ):
            raise ValueError("A production OIDC issuer and JWKS URL are required.")

        if hosted_environment and _is_loopback_service_url(self.database_url):
            raise ValueError(
                "Hosted environments require a non-loopback PostgreSQL database URL. "
                "The local development database must never be used as hosted state."
            )
        if (
            hosted_environment
            and self.operational_database_url is not None
            and _is_loopback_service_url(self.operational_database_url)
        ):
            raise ValueError(
                "Hosted environments require a non-loopback operational database URL."
            )
        if hosted_environment and _is_loopback_service_url(self.valkey_url):
            raise ValueError(
                "Hosted environments require a non-loopback Valkey/Redis URL."
            )
        if hosted_environment and adapter == "KUBERNETES_JOB" and not self.sqs_execution_queue_url:
            raise ValueError(
                "KUBERNETES_JOB execution requires an SQS execution queue in hosted environments."
            )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
