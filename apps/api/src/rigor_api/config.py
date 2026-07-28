from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from urllib.parse import quote

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL


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
    database_host: str | None = None
    database_port: int = 5432
    database_name: str = "rigor"
    database_user: str | None = None
    database_password: SecretStr | None = None
    database_sslmode: str = "require"

    valkey_url: str = "redis://localhost:6381/0"
    valkey_host: str | None = None
    valkey_port: int = 6379
    valkey_database: int = 0
    valkey_auth_token: SecretStr | None = None
    valkey_tls: bool = True

    execution_adapter: str = "LOCAL_FUNCTIONAL"
    execution_dispatch_mode: str = "INLINE"
    execution_queue_url: str | None = None
    execution_cluster_name: str | None = None
    execution_artifact_bucket: str | None = None
    ai_adapter: str = "DETERMINISTIC"
    content_root: Path = Field(default_factory=default_content_root)
    allowed_origins: list[str] = ["http://localhost:3001"]
    oidc_issuer: str = "http://localhost:8002/local-oidc"
    oidc_audience: str = "rigor-web"
    oidc_jwks_url: str | None = None
    local_oidc_enabled: bool = True
    local_oidc_redirect_uris: list[str] = ["http://localhost:3001/auth/callback"]

    def resolved_database_url(self) -> str:
        """Build a production DSN from secret fields when ECS injects them separately."""

        if self.database_host is None:
            return self.database_url
        if self.database_user is None or self.database_password is None:
            raise ValueError(
                "RIGOR_DATABASE_HOST requires RIGOR_DATABASE_USER and RIGOR_DATABASE_PASSWORD"
            )
        return URL.create(
            "postgresql+psycopg",
            username=self.database_user,
            password=self.database_password.get_secret_value(),
            host=self.database_host,
            port=self.database_port,
            database=self.database_name,
            query={"sslmode": self.database_sslmode},
        ).render_as_string(hide_password=False)

    def resolved_valkey_url(self) -> str:
        """Build a TLS Valkey URL from a Secrets Manager token when configured."""

        if self.valkey_host is None:
            return self.valkey_url
        scheme = "rediss" if self.valkey_tls else "redis"
        auth = ""
        if self.valkey_auth_token is not None:
            auth = f":{quote(self.valkey_auth_token.get_secret_value(), safe='')}@"
        return f"{scheme}://{auth}{self.valkey_host}:{self.valkey_port}/{self.valkey_database}"


@lru_cache
def get_settings() -> Settings:
    return Settings()
