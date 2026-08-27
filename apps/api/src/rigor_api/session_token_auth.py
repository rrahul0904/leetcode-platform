from __future__ import annotations

from typing import Any

import jwt
from fastapi import Request
from jwt import ExpiredSignatureError, InvalidTokenError

from .auth import AuthenticationError, TokenValidator


class ClerkSessionTokenValidator(TokenValidator):
    """Validate Clerk session tokens without requiring a custom JWT template.

    Local development continues to use the controlled local OIDC provider. For
    external OIDC, signature, issuer, lifetime, subject, and issued-at are always
    verified. Audience validation is enabled only when RIGOR_JWT_AUDIENCE is
    explicitly configured, which keeps custom JWT templates supported while
    allowing Clerk's standard session token (which has no `aud` claim).
    """

    def validate(self, token: str) -> dict[str, Any]:
        if self.local_provider is not None:
            return super().validate(token)
        if self._jwks_client is None:
            raise AuthenticationError(
                "oidc_not_configured", "The OIDC verifier is not configured"
            )

        try:
            signing_key = self._jwks_client.get_signing_key_from_jwt(token)
            audience = self.settings.jwt_audience
            options: dict[str, object] = {
                "require": ["exp", "iat", "iss", "sub"],
                "verify_aud": bool(audience),
            }
            decoded = jwt.decode(
                token,
                signing_key.key,
                algorithms=["RS256"],
                issuer=self.settings.oidc_issuer,
                audience=audience or None,
                options=options,
            )
            if not audience and not decoded.get("sid"):
                raise AuthenticationError(
                    "session_token_invalid",
                    "A Clerk session token with a session id is required.",
                )
            return decoded
        except AuthenticationError:
            raise
        except ExpiredSignatureError as exc:
            raise AuthenticationError("token_expired", "The bearer token has expired") from exc
        except InvalidTokenError as exc:
            raise AuthenticationError("token_invalid", "The bearer token is invalid") from exc


def session_token_validator(request: Request) -> TokenValidator:
    """Return the lifespan-created validator, wrapping external Clerk only.

    FastAPI's application state is initialized during lifespan startup rather than
    module import. Resolving here keeps imports side-effect free and lets tests,
    local OIDC, and Vercel share the same application composition.
    """

    base: TokenValidator = request.app.state.token_validator
    if base.local_provider is not None:
        return base

    cached = getattr(request.app.state, "clerk_session_token_validator", None)
    if isinstance(cached, ClerkSessionTokenValidator):
        return cached

    wrapped = ClerkSessionTokenValidator(base.settings, base.local_provider)
    request.app.state.clerk_session_token_validator = wrapped
    return wrapped
