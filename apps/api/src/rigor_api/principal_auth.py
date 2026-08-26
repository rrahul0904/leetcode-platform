from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy import Engine, text

from .auth import (
    ROLE_PERMISSIONS,
    AuthenticationError,
    TokenValidator,
    bearer_scheme,
    token_validator,
)
from .database import database_engine
from .schemas import AuthenticatedPrincipal, Role


def _permissions(roles: list[Role]) -> list[str]:
    return sorted({permission for role in roles for permission in ROLE_PERMISSIONS[role]})


def _issued_at(claims: dict[str, object]) -> datetime:
    try:
        return datetime.fromtimestamp(int(str(claims["iat"])), tz=UTC)
    except (KeyError, TypeError, ValueError) as exc:
        raise AuthenticationError(
            "principal_claims_invalid", "The token issued-at claim is invalid"
        ) from exc


def _local_principal(request: Request, claims: dict[str, object]) -> AuthenticatedPrincipal:
    try:
        raw_roles = claims.get("roles", [])
        if not isinstance(raw_roles, list):
            raise ValueError("roles must be a list")
        roles = [Role(str(value)) for value in raw_roles]
        if not roles:
            raise ValueError("missing roles")
        email = str(claims["email"])
        subject = str(claims["sub"])
        if not email or not subject:
            raise ValueError("missing local identity")
        return AuthenticatedPrincipal(
            subject_id=subject,
            email=email,
            display_name=str(claims.get("name") or email),
            organization_id=(
                str(claims["organization_id"])
                if claims.get("organization_id")
                else None
            ),
            roles=roles,
            permissions=_permissions(roles),
            authentication_provider=str(
                claims.get("auth_provider") or claims.get("iss") or "local"
            ),
            token_issued_at=_issued_at(claims),
            correlation_id=request.state.correlation_id,
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise AuthenticationError(
            "principal_claims_invalid", "Required local principal claims are invalid"
        ) from exc


def _database_principal(
    request: Request,
    engine: Engine,
    claims: dict[str, object],
) -> AuthenticatedPrincipal:
    subject = str(claims.get("sub") or "")
    if not subject:
        raise AuthenticationError("principal_claims_invalid", "The subject claim is missing")

    with engine.connect() as connection:
        user = connection.execute(
            text(
                """
                SELECT id, email, display_name, auth_provider, status
                FROM users
                WHERE identity_subject=:subject
                """
            ),
            {"subject": subject},
        ).mappings().one_or_none()
        if user is None:
            raise AuthenticationError(
                "account_not_provisioned",
                "The authenticated identity has not been provisioned in SkillForge yet.",
            )
        if user["status"] != "active":
            raise AuthenticationError(
                "account_inactive", "The SkillForge account is not active."
            )

        role_values = connection.execute(
            text(
                """
                SELECT role_slug
                FROM user_roles
                WHERE user_id=:user_id
                ORDER BY role_slug
                """
            ),
            {"user_id": user["id"]},
        ).scalars().all()
        try:
            roles = [Role(str(value)) for value in role_values]
        except ValueError as exc:
            raise AuthenticationError(
                "account_roles_invalid", "The SkillForge account has an invalid role assignment."
            ) from exc
        if not roles:
            raise AuthenticationError(
                "account_roles_missing", "The SkillForge account has no assigned role."
            )

        requested_org = claims.get("organization_id") or claims.get("org_id")
        organization_id: str | None = None
        if requested_org:
            organization_id = connection.execute(
                text(
                    """
                    SELECT organization_id::text
                    FROM organization_memberships
                    WHERE user_id=:user_id
                      AND organization_id::text=:organization_id
                      AND status='active'
                    """
                ),
                {"user_id": user["id"], "organization_id": str(requested_org)},
            ).scalar_one_or_none()
            if organization_id is None:
                raise AuthenticationError(
                    "organization_access_denied",
                    "The authenticated user is not an active member of this organization.",
                )

    return AuthenticatedPrincipal(
        subject_id=subject,
        email=str(user["email"]),
        display_name=str(user["display_name"]),
        organization_id=organization_id,
        roles=roles,
        permissions=_permissions(roles),
        authentication_provider=str(user["auth_provider"]),
        token_issued_at=_issued_at(claims),
        correlation_id=request.state.correlation_id,
    )


async def database_authoritative_principal(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    validator: Annotated[TokenValidator, Depends(token_validator)],
    engine: Annotated[Engine, Depends(database_engine)],
) -> AuthenticatedPrincipal:
    """Authenticate with OIDC; authorize from SkillForge PostgreSQL.

    Local development identities keep their controlled token roles. External OIDC
    tokens (Clerk/Auth0) prove identity only: account status, roles, permissions,
    display data, and organization access are loaded from PostgreSQL. This prevents
    a provider-side/custom JWT role claim from escalating SkillForge privileges.
    """

    if credentials is None or credentials.scheme.casefold() != "bearer":
        raise AuthenticationError("authentication_required", "A bearer token is required")
    claims = validator.validate(credentials.credentials)
    if validator.local_provider is not None:
        return _local_principal(request, claims)
    return _database_principal(request, engine, claims)
