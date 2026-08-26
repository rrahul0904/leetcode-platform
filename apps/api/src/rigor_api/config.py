from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Self

from pydantic import AliasChoices, Field, model_validator
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


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="RIGOR_", env_file=".env", extra="ignore")

    environment: str = "development"
    database_url: str = "postgresql+psycopg://rigor:rigor_local_only@localhost:5434/rigor"
    operational_database_url: str | None = None
    valkey_url: str = "redis://localhost:6381/0"
    execution_adapter: str = "LOCAL_FUNCTIONAL"
    ai_adapter: str = "DETERMINISTIC"
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
        local_only_adapters = {"LOCAL_FUNCTIONAL", "LOCAL_DOCKER"}
        if environment in {"production", "staging"} and adapter in local_only_adapters:
            raise ValueError(
                f"{adapter} candidate execution is forbidden in staging and production. "
                "Configure the isolated SQS-backed execution plane instead."
            )
        if environment in {"production", "staging"} and not self.local_oidc_enabled:
            if not self.oidc_jwks_url or not self.oidc_issuer:
                raise ValueError("A production OIDC issuer and JWKS URL are required.")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
