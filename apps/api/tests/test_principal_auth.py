from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import UUID

import pytest
from rigor_api.auth import AuthenticationError
from rigor_api.persistence import ensure_user, synchronize_local_user_roles
from rigor_api.principal_auth import _database_principal
from rigor_api.schemas import AuthenticatedPrincipal, Role


def _request() -> SimpleNamespace:
    return SimpleNamespace(state=SimpleNamespace(correlation_id="corr-123"))


def _database_engine(
    *,
    status: str = "active",
    roles: list[str] | None = None,
    present: bool = True,
) -> MagicMock:
    engine = MagicMock()
    connection = MagicMock()
    context = MagicMock()
    context.__enter__.return_value = connection
    engine.connect.return_value = context

    user_result = MagicMock()
    user_result.mappings.return_value.one_or_none.return_value = (
        {
            "id": "5f184f4c-05ab-4c0a-89dc-22cf1a80d31d",
            "email": "candidate@example.com",
            "display_name": "Database User",
            "auth_provider": "clerk",
            "status": status,
        }
        if present
        else None
    )
    role_result = MagicMock()
    role_result.scalars.return_value.all.return_value = roles or []
    connection.execute.side_effect = [user_result, role_result]
    return engine


def _principal(*, provider: str = "clerk") -> AuthenticatedPrincipal:
    roles = [Role.candidate]
    return AuthenticatedPrincipal(
        subject_id="user_clerk_123",
        email="candidate@example.com",
        display_name="Candidate One",
        organization_id=None,
        roles=roles,
        permissions=["catalog:read", "submission:create"],
        authentication_provider=provider,
        token_issued_at=datetime(2026, 8, 26, tzinfo=UTC),
        correlation_id="corr-123",
    )


def test_external_provider_role_claim_cannot_escalate_database_role() -> None:
    principal = _database_principal(
        _request(),
        _database_engine(roles=["candidate"]),
        {
            "sub": "user_clerk_123",
            "iat": int(datetime(2026, 8, 26, tzinfo=UTC).timestamp()),
            "roles": ["platform-administrator"],
            "email": "attacker-controlled@example.com",
        },
    )

    assert [role.value for role in principal.roles] == ["candidate"]
    assert "user:manage" not in principal.permissions
    assert "submission:create" in principal.permissions
    assert principal.email == "candidate@example.com"
    assert principal.authentication_provider == "clerk"


def test_database_admin_remains_admin_when_external_token_omits_roles() -> None:
    principal = _database_principal(
        _request(),
        _database_engine(roles=["platform-administrator"]),
        {
            "sub": "user_clerk_123",
            "iat": int(datetime(2026, 8, 26, tzinfo=UTC).timestamp()),
        },
    )

    assert [role.value for role in principal.roles] == ["platform-administrator"]
    assert "user:manage" in principal.permissions


def test_unknown_external_identity_is_not_silently_provisioned() -> None:
    with pytest.raises(AuthenticationError) as exc_info:
        _database_principal(
            _request(),
            _database_engine(present=False),
            {
                "sub": "unknown_clerk_user",
                "iat": int(datetime(2026, 8, 26, tzinfo=UTC).timestamp()),
            },
        )

    assert exc_info.value.code == "account_not_provisioned"


@pytest.mark.parametrize("status", ["disabled", "deleted"])
def test_inactive_database_account_is_denied(status: str) -> None:
    with pytest.raises(AuthenticationError) as exc_info:
        _database_principal(
            _request(),
            _database_engine(status=status, roles=["candidate"]),
            {
                "sub": "user_clerk_123",
                "iat": int(datetime(2026, 8, 26, tzinfo=UTC).timestamp()),
            },
        )

    assert exc_info.value.code == "account_inactive"


def test_normal_request_identity_refresh_does_not_mutate_user_roles() -> None:
    connection = MagicMock()
    result = MagicMock()
    result.scalar_one.return_value = UUID("5f184f4c-05ab-4c0a-89dc-22cf1a80d31d")
    connection.execute.return_value = result

    user_id = ensure_user(connection, _principal())

    assert user_id == UUID("5f184f4c-05ab-4c0a-89dc-22cf1a80d31d")
    assert connection.execute.call_count == 1
    statement = str(connection.execute.call_args.args[0])
    assert "user_roles" not in statement


def test_external_principal_cannot_use_local_role_synchronizer() -> None:
    connection = MagicMock()
    with pytest.raises(ValueError, match="controlled local OIDC"):
        synchronize_local_user_roles(
            connection,
            _principal(provider="clerk"),
            UUID("5f184f4c-05ab-4c0a-89dc-22cf1a80d31d"),
        )
    connection.execute.assert_not_called()
