from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

from rigor_api.principal_auth import _database_principal


def test_external_provider_role_claim_cannot_escalate_database_role() -> None:
    request = SimpleNamespace(state=SimpleNamespace(correlation_id="corr-123"))
    engine = MagicMock()
    connection = MagicMock()
    context = MagicMock()
    context.__enter__.return_value = connection
    engine.connect.return_value = context

    user_result = MagicMock()
    user_result.mappings.return_value.one_or_none.return_value = {
        "id": "5f184f4c-05ab-4c0a-89dc-22cf1a80d31d",
        "email": "candidate@example.com",
        "display_name": "Candidate One",
        "auth_provider": "clerk",
        "status": "active",
    }
    role_result = MagicMock()
    role_result.scalars.return_value.all.return_value = ["candidate"]
    connection.execute.side_effect = [user_result, role_result]

    principal = _database_principal(
        request,
        engine,
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
