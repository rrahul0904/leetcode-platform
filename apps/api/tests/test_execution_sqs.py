from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime

from rigor_api.execution_sqs import AwsCredentials, SqsJsonClient


@dataclass
class FakeTransport:
    responses: list[bytes]
    calls: list[dict[str, object]] = field(default_factory=list)

    def post(
        self,
        url: str,
        *,
        headers: dict[str, str],
        body: bytes,
        timeout_seconds: float,
    ) -> bytes:
        self.calls.append(
            {
                "url": url,
                "headers": headers,
                "body": body,
                "timeout_seconds": timeout_seconds,
            }
        )
        return self.responses.pop(0)


def client(transport: FakeTransport) -> SqsJsonClient:
    return SqsJsonClient(
        queue_url="https://sqs.us-east-1.amazonaws.com/123456789012/rigor-execution",
        region="us-east-1",
        credentials=AwsCredentials(
            access_key_id="AKIDEXAMPLE",
            secret_access_key="secret",
            session_token="session-token",
        ),
        transport=transport,
    )


def test_send_message_uses_sqs_json_protocol_and_sigv4_headers() -> None:
    transport = FakeTransport([b'{"MessageId":"message-1"}'])
    sqs = client(transport)

    assert sqs.send_message('{"schema_version":1}') == "message-1"

    call = transport.calls[0]
    assert call["url"] == "https://sqs.us-east-1.amazonaws.com/"
    headers = call["headers"]
    assert isinstance(headers, dict)
    assert headers["Content-Type"] == "application/x-amz-json-1.0"
    assert headers["X-Amz-Target"] == "AmazonSQS.SendMessage"
    assert headers["X-Amz-Security-Token"] == "session-token"
    assert str(headers["Authorization"]).startswith("AWS4-HMAC-SHA256 Credential=AKIDEXAMPLE/")
    body = json.loads(call["body"])
    assert body == {
        "QueueUrl": "https://sqs.us-east-1.amazonaws.com/123456789012/rigor-execution",
        "MessageBody": '{"schema_version":1}',
    }


def test_receive_and_delete_use_receipt_handle_without_mutating_message_body() -> None:
    transport = FakeTransport(
        [
            json.dumps(
                {
                    "Messages": [
                        {
                            "MessageId": "message-1",
                            "ReceiptHandle": "receipt-1",
                            "Body": '{"event_type":"execution.requested"}',
                        }
                    ]
                }
            ).encode(),
            b"{}",
        ]
    )
    sqs = client(transport)

    messages = sqs.receive_messages(maximum=1, wait_seconds=0, visibility_timeout=60)
    assert len(messages) == 1
    assert messages[0].body == '{"event_type":"execution.requested"}'
    assert messages[0].receipt_handle == "receipt-1"

    sqs.delete_message(messages[0].receipt_handle)
    delete_call = transport.calls[1]
    assert json.loads(delete_call["body"]) == {
        "QueueUrl": "https://sqs.us-east-1.amazonaws.com/123456789012/rigor-execution",
        "ReceiptHandle": "receipt-1",
    }


def test_signing_is_deterministic_for_fixed_time() -> None:
    transport = FakeTransport([b'{"MessageId":"message-1"}'])
    sqs = client(transport)
    fixed = datetime(2026, 7, 29, 2, 30, tzinfo=UTC)

    response = sqs._call(
        "SendMessage",
        {
            "QueueUrl": sqs.queue_url,
            "MessageBody": "bounded",
        },
        now=fixed,
    )

    assert response["MessageId"] == "message-1"
    headers = transport.calls[0]["headers"]
    assert isinstance(headers, dict)
    assert headers["X-Amz-Date"] == "20260729T023000Z"
    assert "/20260729/us-east-1/sqs/aws4_request" in str(headers["Authorization"])
