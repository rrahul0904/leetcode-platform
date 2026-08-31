from __future__ import annotations

from unittest.mock import MagicMock
from uuid import UUID

from fastapi.security import HTTPAuthorizationCredentials
from rigor_api.saas_routes import IdentityReconcileRequest, reconcile_clerk_identity


def _engine_with_existing_user(*, status: str) -> tuple[MagicMock, MagicMock]:
    engine = MagicMock()
    connection = MagicMock()
    context = MagicMock()
    context.__enter__.return_value = connection
    engine.begin.return_value = context

    user_result = MagicMock()
    user_result.mappings.return_value.one.return_value = {
        "id": UUID("22222222-2222-2222-2222-222222222222"),
        "status": status,
    }
    connection.execute.side_effect = [
        user_result,
        MagicMock(),
        MagicMock(),
        MagicMock(),
        MagicMock(),
        MagicMock(),
    ]
    return engine, connection


def test_reconciliation_preserves_database_status_and_only_bootstraps_when_no_roles() -> None:
    engine, connection = _engine_with_existing_user(status="deleted")
    validator = MagicMock()
    validator.local_provider = None
    validator.validate.return_value = {"sub": "user_clerk_existing"}

    response = reconcile_clerk_identity(
        IdentityReconcileRequest(
            subject="user_clerk_existing",
            email="candidate@example.com",
            email_verified=True,
            display_name="Candidate Existing",
        ),
        engine,
        HTTPAuthorizationCredentials(scheme="Bearer", credentials="signed-token"),
        validator,
    )

    assert response.status == "deleted"
    user_upsert = str(connection.execute.call_args_list[0].args[0])
    conflict_update = user_upsert.split("ON CONFLICT", maxsplit=1)[1]
    assert "status='active'" not in conflict_update
    assert "deleted_at" not in conflict_update

    role_provisioning = str(connection.execute.call_args_list[1].args[0])
    assert "WHERE NOT EXISTS" in role_provisioning
    assert "SELECT 1 FROM user_roles" in role_provisioning


def test_reconciliation_rejects_subject_mismatch_before_database_write() -> None:
    engine = MagicMock()
    validator = MagicMock()
    validator.local_provider = None
    validator.validate.return_value = {"sub": "different_subject"}

    try:
        reconcile_clerk_identity(
            IdentityReconcileRequest(
                subject="requested_subject",
                email="candidate@example.com",
                email_verified=True,
                display_name="Candidate Existing",
            ),
            engine,
            HTTPAuthorizationCredentials(scheme="Bearer", credentials="signed-token"),
            validator,
        )
    except Exception as exc:
        assert getattr(exc, "code", None) == "identity_subject_mismatch"
    else:
        raise AssertionError("Subject mismatch was unexpectedly accepted")

    engine.begin.assert_not_called()
