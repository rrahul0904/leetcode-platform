from rigor_api.database import normalize_database_url


def test_normalize_database_url_uses_psycopg_for_neon_urls() -> None:
    assert (
        normalize_database_url("postgres://user:pass@example.neon.tech/db?sslmode=require")
        == "postgresql+psycopg://user:pass@example.neon.tech/db?sslmode=require"
    )
    assert (
        normalize_database_url("postgresql://user:pass@example.neon.tech/db?sslmode=require")
        == "postgresql+psycopg://user:pass@example.neon.tech/db?sslmode=require"
    )


def test_normalize_database_url_preserves_explicit_driver() -> None:
    value = "postgresql+psycopg://user:pass@example.neon.tech/db?sslmode=require"
    assert normalize_database_url(value) == value
