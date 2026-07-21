from __future__ import annotations

import base64
import hashlib
from typing import cast
from urllib.parse import parse_qs, urlparse

from fastapi.testclient import TestClient
from rigor_api.auth import LocalOIDCProvider
from rigor_api.main import app

VERIFIER = "test-verifier-that-is-long-enough-for-pkce-validation-1234567890"
REDIRECT_URI = "http://localhost:3001/auth/callback"


def challenge(verifier: str = VERIFIER) -> str:
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def sign_in(client: TestClient, identity: str = "candidate") -> str:
    authorization = client.get(
        "/local-oidc/authorize",
        params={
            "client_id": "rigor-web",
            "redirect_uri": REDIRECT_URI,
            "response_type": "code",
            "state": "state-value-long-enough",
            "code_challenge": challenge(),
            "code_challenge_method": "S256",
            "identity": identity,
        },
        follow_redirects=False,
    )
    assert authorization.status_code == 302
    code = parse_qs(urlparse(authorization.headers["location"]).query)["code"][0]
    token = client.post(
        "/local-oidc/token",
        json={
            "grant_type": "authorization_code",
            "code": code,
            "client_id": "rigor-web",
            "redirect_uri": REDIRECT_URI,
            "code_verifier": VERIFIER,
        },
    )
    assert token.status_code == 200
    return str(token.json()["access_token"])


def test_local_oidc_discovery_pkce_and_principal_contract() -> None:
    with TestClient(app) as client:
        discovery = client.get("/local-oidc/.well-known/openid-configuration")
        assert discovery.status_code == 200
        assert discovery.json()["code_challenge_methods_supported"] == ["S256"]
        assert client.get("/local-oidc/jwks.json").json()["keys"][0]["alg"] == "RS256"

        access_token = sign_in(client)
        me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {access_token}"})
        assert me.status_code == 200
        principal = me.json()
        assert principal["subject_id"] == "local-candidate"
        assert principal["roles"] == ["candidate"]
        assert "submission:create" in principal["permissions"]
        assert principal["authentication_provider"] == "local-oidc"
        assert principal["correlation_id"] == me.headers["x-correlation-id"]


def test_anonymous_invalid_and_expired_tokens_are_unauthorized() -> None:
    with TestClient(app) as client:
        anonymous = client.get("/api/v1/auth/me")
        assert anonymous.status_code == 401
        assert anonymous.json()["code"] == "authentication_required"
        assert anonymous.headers["www-authenticate"] == "Bearer"

        invalid = client.get("/api/v1/auth/me", headers={"Authorization": "Bearer not-a-jwt"})
        assert invalid.status_code == 401
        assert invalid.json()["code"] == "token_invalid"

        provider = cast(LocalOIDCProvider, app.state.local_oidc_provider)
        expired_token = provider.issue_test_access_token("candidate", expires_in=-1)
        expired = client.get(
            "/api/v1/auth/me", headers={"Authorization": f"Bearer {expired_token}"}
        )
        assert expired.status_code == 401
        assert expired.json()["code"] == "token_expired"


def test_authorization_codes_are_single_use_and_pkce_is_enforced() -> None:
    with TestClient(app) as client:
        authorization = client.get(
            "/local-oidc/authorize",
            params={
                "client_id": "rigor-web",
                "redirect_uri": REDIRECT_URI,
                "state": "state-value-long-enough",
                "code_challenge": challenge(),
                "identity": "candidate",
            },
            follow_redirects=False,
        )
        code = parse_qs(urlparse(authorization.headers["location"]).query)["code"][0]
        payload = {
            "grant_type": "authorization_code",
            "code": code,
            "client_id": "rigor-web",
            "redirect_uri": REDIRECT_URI,
            "code_verifier": "wrong-verifier-that-is-still-long-enough-for-pkce-1234567890",
        }
        rejected = client.post("/local-oidc/token", json=payload)
        assert rejected.status_code == 401
        assert rejected.json()["code"] == "invalid_pkce_verifier"

        payload["code_verifier"] = VERIFIER
        reused = client.post("/local-oidc/token", json=payload)
        assert reused.status_code == 401
        assert reused.json()["code"] == "invalid_authorization_code"
