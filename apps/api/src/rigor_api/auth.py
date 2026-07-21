from __future__ import annotations

import base64
import hashlib
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any
from urllib.parse import urlencode
from uuid import uuid4

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import ExpiredSignatureError, InvalidTokenError, PyJWKClient

from .config import Settings
from .schemas import AuthenticatedPrincipal, Role

ROLE_PERMISSIONS: dict[Role, frozenset[str]] = {
    Role.candidate: frozenset(
        {
            "catalog:read",
            "profile:read",
            "profile:write",
            "submission:create",
            "submission:read-own",
        }
    ),
    Role.content_author: frozenset(
        {
            "catalog:read",
            "content:create",
            "content:edit-own",
            "content:read-private",
            "content:authoring",
        }
    ),
    Role.technical_reviewer: frozenset(
        {"catalog:read", "content:read-private", "review:read", "review:technical"}
    ),
    Role.editorial_reviewer: frozenset(
        {"catalog:read", "content:read-private", "review:read", "review:editorial"}
    ),
    Role.platform_administrator: frozenset(
        {
            "audit:read",
            "catalog:read",
            "content:publish",
            "content:import",
            "content:authoring",
            "content:read-private",
            "content:transition",
            "review:assign",
            "review:read",
            "source:manage",
            "source:read",
            "coverage:read",
            "user:manage",
        }
    ),
}


@dataclass(frozen=True)
class LocalIdentity:
    subject_id: str
    email: str
    display_name: str
    roles: tuple[Role, ...]


LOCAL_IDENTITIES: dict[str, LocalIdentity] = {
    "candidate": LocalIdentity(
        "local-candidate", "candidate@rigor.test", "Casey Candidate", (Role.candidate,)
    ),
    "author": LocalIdentity(
        "local-author", "author@rigor.test", "Avery Author", (Role.content_author,)
    ),
    "technical-reviewer": LocalIdentity(
        "local-technical-reviewer",
        "technical-reviewer@rigor.test",
        "Terry Technical",
        (Role.technical_reviewer,),
    ),
    "editorial-reviewer": LocalIdentity(
        "local-editorial-reviewer",
        "editorial-reviewer@rigor.test",
        "Emery Editorial",
        (Role.editorial_reviewer,),
    ),
    "platform-administrator": LocalIdentity(
        "local-platform-administrator",
        "platform-administrator@rigor.test",
        "Parker Platform",
        (Role.platform_administrator,),
    ),
}


class AuthenticationError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class AuthorizationError(Exception):
    def __init__(self, message: str = "The authenticated principal lacks this permission.") -> None:
        super().__init__(message)
        self.code = "forbidden"
        self.message = message


@dataclass(frozen=True)
class AuthorizationCode:
    identity: LocalIdentity
    client_id: str
    redirect_uri: str
    code_challenge: str
    nonce: str | None
    expires_at: datetime


def _base64url(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _permissions(roles: list[Role]) -> list[str]:
    return sorted({permission for role in roles for permission in ROLE_PERMISSIONS[role]})


class LocalOIDCProvider:
    """Controlled, ephemeral authorization-code issuer for local development and tests only."""

    def __init__(self, settings: Settings) -> None:
        if settings.environment == "production":
            raise RuntimeError("The controlled local OIDC provider cannot run in production mode")
        self.issuer = settings.oidc_issuer.rstrip("/")
        self.audience = settings.oidc_audience
        self.redirect_uris = frozenset(settings.local_oidc_redirect_uris)
        self._private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        self._kid = f"local-{uuid4()}"
        self._codes: dict[str, AuthorizationCode] = {}

    def discovery(self) -> dict[str, Any]:
        return {
            "issuer": self.issuer,
            "authorization_endpoint": f"{self.issuer}/authorize",
            "token_endpoint": f"{self.issuer}/token",
            "jwks_uri": f"{self.issuer}/jwks.json",
            "response_types_supported": ["code"],
            "grant_types_supported": ["authorization_code"],
            "subject_types_supported": ["public"],
            "id_token_signing_alg_values_supported": ["RS256"],
            "code_challenge_methods_supported": ["S256"],
            "scopes_supported": ["openid", "email", "profile"],
        }

    def jwks(self) -> dict[str, list[dict[str, Any]]]:
        numbers = self._private_key.public_key().public_numbers()
        return {
            "keys": [
                {
                    "kty": "RSA",
                    "use": "sig",
                    "alg": "RS256",
                    "kid": self._kid,
                    "n": _base64url(numbers.n.to_bytes((numbers.n.bit_length() + 7) // 8, "big")),
                    "e": _base64url(numbers.e.to_bytes((numbers.e.bit_length() + 7) // 8, "big")),
                }
            ]
        }

    def create_authorization_code(
        self,
        *,
        identity_key: str,
        client_id: str,
        redirect_uri: str,
        response_type: str,
        code_challenge: str,
        code_challenge_method: str,
        nonce: str | None,
    ) -> str:
        if response_type != "code" or client_id != self.audience:
            raise AuthenticationError("invalid_authorization_request", "Unsupported OIDC request")
        if redirect_uri not in self.redirect_uris:
            raise AuthenticationError("invalid_redirect_uri", "The redirect URI is not registered")
        if code_challenge_method != "S256" or not re.fullmatch(
            r"[A-Za-z0-9_-]{43,128}", code_challenge
        ):
            raise AuthenticationError(
                "invalid_pkce_challenge", "A valid S256 PKCE challenge is required"
            )
        identity = LOCAL_IDENTITIES.get(identity_key)
        if identity is None:
            raise AuthenticationError(
                "unknown_local_identity", "The local identity is not registered"
            )
        code = _base64url(uuid4().bytes + uuid4().bytes)
        self._codes[code] = AuthorizationCode(
            identity=identity,
            client_id=client_id,
            redirect_uri=redirect_uri,
            code_challenge=code_challenge,
            nonce=nonce,
            expires_at=datetime.now(UTC) + timedelta(minutes=2),
        )
        return code

    def exchange_code(
        self,
        *,
        grant_type: str,
        code: str,
        client_id: str,
        redirect_uri: str,
        code_verifier: str,
    ) -> tuple[str, str, int]:
        if grant_type != "authorization_code":
            raise AuthenticationError(
                "unsupported_grant_type", "Only authorization_code is supported"
            )
        authorization = self._codes.pop(code, None)
        if authorization is None or authorization.expires_at <= datetime.now(UTC):
            raise AuthenticationError(
                "invalid_authorization_code", "The authorization code is invalid or expired"
            )
        if client_id != authorization.client_id or redirect_uri != authorization.redirect_uri:
            raise AuthenticationError(
                "authorization_code_mismatch", "The authorization request does not match"
            )
        challenge = _base64url(hashlib.sha256(code_verifier.encode("ascii")).digest())
        if (
            not re.fullmatch(r"[A-Za-z0-9._~-]{43,128}", code_verifier)
            or challenge != authorization.code_challenge
        ):
            raise AuthenticationError("invalid_pkce_verifier", "PKCE verification failed")
        return self._issue_tokens(authorization.identity, authorization.nonce, expires_in=900)

    def issue_test_access_token(self, identity_key: str, *, expires_in: int) -> str:
        """Issue a local token for automated expiry tests; this is never exposed as an API."""
        identity = LOCAL_IDENTITIES[identity_key]
        access_token, _, _ = self._issue_tokens(identity, None, expires_in=expires_in)
        return access_token

    def _issue_tokens(
        self, identity: LocalIdentity, nonce: str | None, *, expires_in: int
    ) -> tuple[str, str, int]:
        now = datetime.now(UTC)
        base_claims: dict[str, Any] = {
            "iss": self.issuer,
            "aud": self.audience,
            "sub": identity.subject_id,
            "email": identity.email,
            "email_verified": True,
            "name": identity.display_name,
            "roles": [role.value for role in identity.roles],
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(seconds=expires_in)).timestamp()),
            "auth_provider": "local-oidc",
            "jti": str(uuid4()),
        }
        access_token = jwt.encode(
            {**base_claims, "token_use": "access"},
            self._private_key,
            algorithm="RS256",
            headers={"kid": self._kid},
        )
        id_claims = {**base_claims, "token_use": "id"}
        if nonce:
            id_claims["nonce"] = nonce
        id_token = jwt.encode(
            id_claims,
            self._private_key,
            algorithm="RS256",
            headers={"kid": self._kid},
        )
        return access_token, id_token, expires_in

    def decode_access_token(self, token: str) -> dict[str, Any]:
        return jwt.decode(
            token,
            self._private_key.public_key(),
            algorithms=["RS256"],
            audience=self.audience,
            issuer=self.issuer,
            options={"require": ["exp", "iat", "iss", "aud", "sub"]},
        )


class TokenValidator:
    def __init__(self, settings: Settings, local_provider: LocalOIDCProvider | None) -> None:
        self.settings = settings
        self.local_provider = local_provider
        self._jwks_client = (
            PyJWKClient(settings.oidc_jwks_url)
            if local_provider is None and settings.oidc_jwks_url
            else None
        )

    def validate(self, token: str) -> dict[str, Any]:
        try:
            if self.local_provider is not None:
                return self.local_provider.decode_access_token(token)
            if self._jwks_client is None:
                raise AuthenticationError(
                    "oidc_not_configured", "The OIDC verifier is not configured"
                )
            signing_key = self._jwks_client.get_signing_key_from_jwt(token)
            return jwt.decode(
                token,
                signing_key.key,
                algorithms=["RS256"],
                audience=self.settings.oidc_audience,
                issuer=self.settings.oidc_issuer,
                options={"require": ["exp", "iat", "iss", "aud", "sub"]},
            )
        except ExpiredSignatureError as exc:
            raise AuthenticationError("token_expired", "The bearer token has expired") from exc
        except InvalidTokenError as exc:
            raise AuthenticationError("token_invalid", "The bearer token is invalid") from exc


bearer_scheme = HTTPBearer(auto_error=False)


def token_validator(request: Request) -> TokenValidator:
    value: TokenValidator = request.app.state.token_validator
    return value


async def authenticated_principal(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    validator: Annotated[TokenValidator, Depends(token_validator)],
) -> AuthenticatedPrincipal:
    if credentials is None or credentials.scheme.casefold() != "bearer":
        raise AuthenticationError("authentication_required", "A bearer token is required")
    claims = validator.validate(credentials.credentials)
    try:
        roles = [Role(value) for value in claims.get("roles", [])]
        if not roles:
            raise ValueError("missing roles")
        issued_at = datetime.fromtimestamp(int(claims["iat"]), tz=UTC)
        return AuthenticatedPrincipal(
            subject_id=str(claims["sub"]),
            email=str(claims["email"]),
            display_name=str(claims.get("name") or claims["email"]),
            organization_id=str(claims["organization_id"])
            if claims.get("organization_id")
            else None,
            roles=roles,
            permissions=_permissions(roles),
            authentication_provider=str(claims.get("auth_provider") or claims["iss"]),
            token_issued_at=issued_at,
            correlation_id=request.state.correlation_id,
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise AuthenticationError(
            "principal_claims_invalid", "Required principal claims are invalid"
        ) from exc


def require_permissions(*required: str) -> Any:
    async def dependency(
        principal: Annotated[AuthenticatedPrincipal, Depends(authenticated_principal)],
    ) -> AuthenticatedPrincipal:
        missing = set(required) - set(principal.permissions)
        if missing:
            raise AuthorizationError(
                f"Missing required permission(s): {', '.join(sorted(missing))}"
            )
        return principal

    return dependency


def authorization_redirect(redirect_uri: str, code: str, state: str) -> str:
    return f"{redirect_uri}?{urlencode({'code': code, 'state': state})}"
