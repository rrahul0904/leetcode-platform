from __future__ import annotations

import base64
import hashlib
import hmac
import json
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Connection, text


class WebhookVerificationError(ValueError):
    pass


def verify_svix_webhook(
    *,
    body: bytes,
    message_id: str | None,
    timestamp: str | None,
    signatures: str | None,
    secret: str,
    now: datetime | None = None,
    tolerance_seconds: int = 300,
) -> dict[str, Any]:
    if not message_id or not timestamp or not signatures:
        raise WebhookVerificationError("Required Svix signature headers are missing.")
    try:
        event_timestamp = int(timestamp)
    except ValueError as exc:
        raise WebhookVerificationError("Webhook timestamp is invalid.") from exc
    current = int((now or datetime.now(UTC)).timestamp())
    if abs(current - event_timestamp) > tolerance_seconds:
        raise WebhookVerificationError("Webhook timestamp is outside the replay window.")
    encoded_secret = secret[6:] if secret.startswith("whsec_") else secret
    try:
        secret_bytes = base64.b64decode(encoded_secret, validate=True)
    except ValueError as exc:
        raise WebhookVerificationError("Webhook secret is invalid.") from exc
    signed = f"{message_id}.{timestamp}.".encode("utf-8") + body
    expected = base64.b64encode(hmac.new(secret_bytes, signed, hashlib.sha256).digest()).decode()
    candidates = []
    for token in signatures.split():
        if "," in token:
            version, signature = token.split(",", 1)
            if version == "v1":
                candidates.append(signature)
    if not candidates or not any(hmac.compare_digest(expected, value) for value in candidates):
        raise WebhookVerificationError("Webhook signature is invalid.")
    try:
        payload = json.loads(body)
    except json.JSONDecodeError as exc:
        raise WebhookVerificationError("Webhook payload is invalid JSON.") from exc
    if not isinstance(payload, dict):
        raise WebhookVerificationError("Webhook payload must be an object.")
    return payload


def _primary_email(data: dict[str, Any]) -> tuple[str, bool]:
    addresses = data.get("email_addresses")
    primary_id = data.get("primary_email_address_id")
    if not isinstance(addresses, list):
        return ("", False)
    ordered = sorted(
        (item for item in addresses if isinstance(item, dict)),
        key=lambda item: item.get("id") != primary_id,
    )
    for item in ordered:
        email = item.get("email_address")
        if isinstance(email, str) and email:
            verification = item.get("verification")
            verified = isinstance(verification, dict) and verification.get("status") == "verified"
            return email, verified
    return ("", False)


def _display_name(data: dict[str, Any], email: str) -> str:
    parts = [data.get("first_name"), data.get("last_name")]
    value = " ".join(part.strip() for part in parts if isinstance(part, str) and part.strip())
    if value:
        return value[:160]
    username = data.get("username")
    if isinstance(username, str) and username:
        return username[:160]
    return (email or "SkillForge Candidate")[:160]


def process_clerk_event(
    connection: Connection,
    *,
    external_event_id: str,
    payload: dict[str, Any],
) -> str:
    event_type = payload.get("type")
    data = payload.get("data")
    if not isinstance(event_type, str) or not isinstance(data, dict):
        raise ValueError("Clerk event type/data are missing.")
    inserted = connection.execute(
        text(
            """
            INSERT INTO identity_webhook_events(provider, external_event_id, event_type)
            VALUES ('clerk', :event_id, :event_type)
            ON CONFLICT (external_event_id) DO NOTHING
            RETURNING id
            """
        ),
        {"event_id": external_event_id, "event_type": event_type},
    ).scalar_one_or_none()
    if inserted is None:
        return "duplicate"

    status = "processed"
    if event_type in {"user.created", "user.updated"}:
        subject = data.get("id")
        email, verified = _primary_email(data)
        if not isinstance(subject, str) or not subject or not email:
            raise ValueError("Clerk user event is missing identity/email.")
        user_id = connection.execute(
            text(
                """
                INSERT INTO users(
                    identity_subject, email, display_name, email_verified,
                    auth_provider, status, last_login_at
                )
                VALUES (:subject, :email, :display_name, :verified, 'clerk', 'active', NULL)
                ON CONFLICT (identity_subject) DO UPDATE SET
                    email=EXCLUDED.email,
                    display_name=EXCLUDED.display_name,
                    email_verified=EXCLUDED.email_verified,
                    auth_provider='clerk',
                    status='active',
                    deleted_at=NULL,
                    updated_at=CURRENT_TIMESTAMP
                RETURNING id
                """
            ),
            {
                "subject": subject,
                "email": email,
                "display_name": _display_name(data, email),
                "verified": verified,
            },
        ).scalar_one()
        connection.execute(
            text(
                """
                INSERT INTO user_roles(user_id, role_slug)
                VALUES (:user_id, 'candidate')
                ON CONFLICT DO NOTHING
                """
            ),
            {"user_id": user_id},
        )
        connection.execute(
            text(
                """
                INSERT INTO user_preferences(user_id)
                VALUES (:user_id)
                ON CONFLICT (user_id) DO NOTHING
                """
            ),
            {"user_id": user_id},
        )
    elif event_type == "user.deleted":
        subject = data.get("id")
        if isinstance(subject, str) and subject:
            connection.execute(
                text(
                    """
                    UPDATE users SET status='deleted', deleted_at=CURRENT_TIMESTAMP,
                                     updated_at=CURRENT_TIMESTAMP
                    WHERE identity_subject=:subject
                    """
                ),
                {"subject": subject},
            )
    elif event_type == "session.created":
        subject = data.get("user_id")
        session_id = data.get("id")
        if isinstance(subject, str) and subject:
            connection.execute(
                text(
                    """
                    INSERT INTO login_events(
                        user_id, auth_provider, external_subject, session_reference, success
                    )
                    SELECT id, 'clerk', identity_subject, :session_id, true
                    FROM users WHERE identity_subject=:subject
                    """
                ),
                {"subject": subject, "session_id": str(session_id) if session_id else None},
            )
            connection.execute(
                text("UPDATE users SET last_login_at=CURRENT_TIMESTAMP WHERE identity_subject=:subject"),
                {"subject": subject},
            )
    else:
        status = "ignored"

    connection.execute(
        text(
            """
            UPDATE identity_webhook_events
            SET status=:status, processed_at=CURRENT_TIMESTAMP
            WHERE external_event_id=:event_id
            """
        ),
        {"status": status, "event_id": external_event_id},
    )
    return status
