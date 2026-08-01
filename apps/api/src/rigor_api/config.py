from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Self

from pydantic import Field, model_validator
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

    @model_validator(mode="after")
    def production_execution_must_fail_closed(self) -> Self:
        environment = self.environment.strip().lower()
        adapter = self.execution_adapter.strip().upper()
        if environment in {"production", "staging"} and adapter == "LOCAL_FUNCTIONAL":
            raise ValueError(
                "LOCAL_FUNCTIONAL candidate execution is forbidden in staging and production. "
                "Configure the isolated Kubernetes execution plane instead."
            )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
