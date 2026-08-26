from __future__ import annotations

import base64
import hashlib
import hmac
import json
from datetime import UTC, datetime

import pytest

from rigor_api.execution_sqs import AwsCredentials, StaticCredentialProvider
from rigor_api.identity_webhooks import WebhookVerificationError, verify_svix_webhook
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
