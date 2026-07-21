from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
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
    content_root: Path = Field(default_factory=default_content_root)
    allowed_origins: list[str] = ["http://localhost:3001"]
    oidc_issuer: str = "http://localhost:8002/local-oidc"
    oidc_audience: str = "rigor-web"
    oidc_jwks_url: str | None = None
    local_oidc_enabled: bool = True
    local_oidc_redirect_uris: list[str] = ["http://localhost:3001/auth/callback"]


@lru_cache
def get_settings() -> Settings:
    return Settings()
