from __future__ import annotations

import base64
import hashlib
import hmac
import json
from datetime import UTC, datetime
from unittest.mock import MagicMock
from uuid import UUID

import pytest
from rigor_api.execution_sqs import AwsCredentials, StaticCredentialProvider
from rigor_api.identity_webhooks import (
    WebhookVerificationError,
    process_clerk_event,
    verify_svix_webhook,
)
from rigor_api.object_storage import S3Presigner


def _signed_headers(body: bytes, secret: str, message_id: str, timestamp: int) -> dict[str, str]:
    key = base64.b64decode(secret.removeprefix("whsec_"))
    signed = f"{message_id}.{timestamp}.".encode() + body
    signature = base64.b64encode(hmac.new(key, signed, hashlib.sha256).digest()).decode()
    return {
        "svix-id": message_id,
        "svix-timestamp": str(timestamp),
        "svix-signature": f"v1,{signature}",
    }


def test_clerk_svix_signature_verification_and_replay_window() -> None:
    now = datetime(2026, 8, 26, 12, 0, tzinfo=UTC)
    body = json.dumps({"type": "user.created", "data": {"id": "user_123"}}).encode()
    secret = "whsec_" + base64.b64encode(b"skillforge-test-secret").decode()
    headers = _signed_headers(body, secret, "msg_123", int(now.timestamp()))
    payload = verify_svix_webhook(
        body=body,
        message_id=headers["svix-id"],
        timestamp=headers["svix-timestamp"],
        signatures=headers["svix-signature"],
        secret=secret,
        now=now,
    )
    assert payload["type"] == "user.created"
    with pytest.raises(WebhookVerificationError):
        verify_svix_webhook(
            body=body,
            message_id="msg_123",
            timestamp=str(int(now.timestamp()) - 301),
            signatures=headers["svix-signature"],
            secret=secret,
            now=now,
        )


def test_clerk_user_update_preserves_database_account_state_and_existing_roles() -> None:
    connection = MagicMock()
    event_result = MagicMock()
    event_result.scalar_one_or_none.return_value = UUID(
        "11111111-1111-1111-1111-111111111111"
    )
    user_result = MagicMock()
    user_result.scalar_one.return_value = UUID("22222222-2222-2222-2222-222222222222")
    connection.execute.side_effect = [
        event_result,
        user_result,
        MagicMock(),
        MagicMock(),
        MagicMock(),
        MagicMock(),
        MagicMock(),
        MagicMock(),
    ]

    outcome = process_clerk_event(
        connection,
        external_event_id="evt-user-update-1",
        payload={
            "type": "user.updated",
            "data": {
                "id": "user_clerk_123",
                "primary_email_address_id": "email_1",
                "email_addresses": [
                    {
                        "id": "email_1",
                        "email_address": "candidate@example.com",
                        "verification": {"status": "verified"},
                    }
                ],
                "first_name": "Candidate",
                "last_name": "One",
            },
        },
    )

    assert outcome == "processed"
    user_upsert = str(connection.execute.call_args_list[1].args[0])
    conflict_update = user_upsert.split("ON CONFLICT", maxsplit=1)[1]
    assert "status='active'" not in conflict_update
    assert "deleted_at=NULL" not in conflict_update

    role_provisioning = str(connection.execute.call_args_list[2].args[0])
    assert "WHERE NOT EXISTS" in role_provisioning
    assert "SELECT 1 FROM user_roles" in role_provisioning


def test_s3_presigner_is_short_lived_and_never_exposes_secret() -> None:
    provider = StaticCredentialProvider(
        AwsCredentials("AKIATEST", "top-secret", "session-token")
    )
    signer = S3Presigner(
        region="us-east-1",
        bucket="skillforge-private",
        credential_provider=provider,
    )
    url = signer.presign(
        method="PUT",
        storage_key="candidates/abc/resume.pdf",
        expires_seconds=300,
        now=datetime(2026, 8, 26, 12, 0, tzinfo=UTC),
    )
    assert "X-Amz-Expires=300" in url
    assert "X-Amz-Signature=" in url
    assert "top-secret" not in url
    assert "session-token" in url
