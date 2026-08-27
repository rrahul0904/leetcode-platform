from __future__ import annotations

import pytest

from rigor_api.auth import AuthenticationError
from rigor_api.config import Settings
from rigor_api.session_token_auth import ClerkSessionTokenValidator


class _SigningKey:
    key = object()


class _JwksClient:
    def get_signing_key_from_jwt(self, _token: str) -> _SigningKey:
        return _SigningKey()


def _settings(*, audience: str | None = None) -> Settings:
    settings = Settings(
        environment="production",
        local_oidc_enabled=False,
        execution_adapter="VERCEL_SANDBOX",
        oidc_issuer="https://skillforge.clerk.accounts.dev",
        oidc_jwks_url="https://skillforge.clerk.accounts.dev/.well-known/jwks.json",
    )
    settings.jwt_audience = audience
    return settings


def _validator(*, audience: str | None = None) -> ClerkSessionTokenValidator:
    validator = ClerkSessionTokenValidator(_settings(audience=audience), None)
    validator._jwks_client = _JwksClient()  # type: ignore[assignment]
    return validator


def test_standard_clerk_session_token_does_not_require_audience(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    def fake_decode(*_args: object, **kwargs: object) -> dict[str, object]:
        captured.update(kwargs)
        return {
            "sub": "user_123",
            "sid": "sess_123",
            "iss": "https://skillforge.clerk.accounts.dev",
            "iat": 1,
            "exp": 2,
        }

    monkeypatch.setattr("rigor_api.session_token_auth.jwt.decode", fake_decode)
    claims = _validator().validate("session-token")

    assert claims["sub"] == "user_123"
    assert captured["audience"] is None
    assert captured["options"] == {
        "require": ["exp", "iat", "iss", "sub"],
        "verify_aud": False,
    }


def test_standard_clerk_session_token_requires_session_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "rigor_api.session_token_auth.jwt.decode",
        lambda *_args, **_kwargs: {
            "sub": "user_123",
            "iss": "https://skillforge.clerk.accounts.dev",
            "iat": 1,
            "exp": 2,
        },
    )

    with pytest.raises(AuthenticationError, match="session id"):
        _validator().validate("not-a-session-token")


def test_custom_template_can_keep_explicit_audience(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    def fake_decode(*_args: object, **kwargs: object) -> dict[str, object]:
        captured.update(kwargs)
        return {
            "sub": "user_123",
            "iss": "https://skillforge.clerk.accounts.dev",
            "iat": 1,
            "exp": 2,
        }

    monkeypatch.setattr("rigor_api.session_token_auth.jwt.decode", fake_decode)
    claims = _validator(audience="skillforge-api").validate("custom-token")

    assert claims["sub"] == "user_123"
    assert captured["audience"] == "skillforge-api"
    assert captured["options"] == {
        "require": ["exp", "iat", "iss", "sub"],
        "verify_aud": True,
    }
