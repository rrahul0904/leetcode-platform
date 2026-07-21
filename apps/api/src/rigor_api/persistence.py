from __future__ import annotations

import json
from typing import Any
from uuid import UUID

from sqlalchemy import Connection, text

from .schemas import AuthenticatedPrincipal


def ensure_user(connection: Connection, principal: AuthenticatedPrincipal) -> UUID:
    user_id = connection.execute(
        text(
            """
            INSERT INTO users (
                identity_subject, email, display_name, email_verified, last_login_at
            ) VALUES (
                :subject, :email, :display_name, true, CURRENT_TIMESTAMP
            )
            ON CONFLICT (identity_subject) DO UPDATE SET
                email = EXCLUDED.email,
                display_name = EXCLUDED.display_name,
                email_verified = true,
                last_login_at = CURRENT_TIMESTAMP,
                updated_at = CURRENT_TIMESTAMP
            RETURNING id
            """
        ),
        {
            "subject": principal.subject_id,
            "email": principal.email,
            "display_name": principal.display_name,
        },
    ).scalar_one()
    connection.execute(
        text("DELETE FROM user_roles WHERE user_id = :user_id"), {"user_id": user_id}
    )
    for role in principal.roles:
        connection.execute(
            text("INSERT INTO user_roles (user_id, role_slug) VALUES (:user_id, :role)"),
            {"user_id": user_id, "role": role.value},
        )
    return UUID(str(user_id))


def audit_event(
    connection: Connection,
    principal: AuthenticatedPrincipal,
    actor_user_id: UUID,
    *,
    action: str,
    resource_type: str,
    resource_id: str,
    details: dict[str, Any],
) -> None:
    connection.execute(
        text(
            """
            INSERT INTO audit_events (
                actor_user_id, action, resource_type, resource_id, details, correlation_id
            ) VALUES (
                :actor_user_id, :action, :resource_type, :resource_id,
                CAST(:details AS jsonb), :correlation_id
            )
            """
        ),
        {
            "actor_user_id": actor_user_id,
            "action": action,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "details": json.dumps(details),
            "correlation_id": principal.correlation_id,
        },
    )
