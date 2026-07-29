from __future__ import annotations

import hashlib
import hmac
import json
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol
from urllib import error, parse, request

from .outbox import OutboxMessage

SQS_CONTENT_TYPE = "application/x-amz-json-1.0"
SQS_SERVICE = "sqs"


class SqsTransportError(RuntimeError):
    pass


@dataclass(frozen=True)
class AwsCredentials:
    access_key_id: str
    secret_access_key: str
    session_token: str | None = None

    @classmethod
    def discover(cls) -> AwsCredentials:
        access_key = os.getenv("AWS_ACCESS_KEY_ID")
        secret_key = os.getenv("AWS_SECRET_ACCESS_KEY")
        if access_key and secret_key:
            return cls(
                access_key_id=access_key,
                secret_access_key=secret_key,
                session_token=os.getenv("AWS_SESSION_TOKEN"),
            )

        relative_uri = os.getenv("AWS_CONTAINER_CREDENTIALS_RELATIVE_URI")
        full_uri = os.getenv("AWS_CONTAINER_CREDENTIALS_FULL_URI")
        if relative_uri:
            credential_url = f"http://169.254.170.2{relative_uri}"
        elif full_uri:
            parsed = parse.urlsplit(full_uri)
            if parsed.scheme != "http" or parsed.hostname not in {
                "169.254.170.2",
                "127.0.0.1",
                "localhost",
            }:
                raise SqsTransportError("Untrusted ECS credential endpoint configuration.")
            credential_url = full_uri
        else:
            raise SqsTransportError("AWS credentials are unavailable to the trusted queue worker.")

        try:
            with request.urlopen(credential_url, timeout=2.0) as response:
                payload = json.loads(response.read(32 * 1024))
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            raise SqsTransportError("Unable to load ECS task credentials.") from exc
        if not isinstance(payload, dict):
            raise SqsTransportError("ECS credential response is invalid.")
        access_key = payload.get("AccessKeyId")
        secret_key = payload.get("SecretAccessKey")
        token = payload.get("Token")
        if not isinstance(access_key, str) or not isinstance(secret_key, str):
            raise SqsTransportError("ECS credential response is incomplete.")
        return cls(
            access_key_id=access_key,
            secret_access_key=secret_key,
            session_token=str(token) if token else None,
        )


class HttpTransport(Protocol):
    def post(
        self,
        url: str,
        *,
        headers: dict[str, str],
        body: bytes,
        timeout_seconds: float,
    ) -> bytes: ...


class UrllibTransport:
    def post(
        self,
        url: str,
        *,
        headers: dict[str, str],
        body: bytes,
        timeout_seconds: float,
    ) -> bytes:
        http_request = request.Request(url, data=body, headers=headers, method="POST")
        try:
            with request.urlopen(http_request, timeout=timeout_seconds) as response:
                return response.read(1024 * 1024)
        except error.HTTPError as exc:
            detail = exc.read(16 * 1024).decode("utf-8", errors="replace")
            raise SqsTransportError(f"SQS HTTP {exc.code}: {detail[:1000]}") from exc
        except OSError as exc:
            raise SqsTransportError("SQS transport failed.") from exc


def _hmac(key: bytes, value: str) -> bytes:
    return hmac.new(key, value.encode("utf-8"), hashlib.sha256).digest()


def _signing_key(secret_key: str, date_stamp: str, region: str) -> bytes:
    date_key = _hmac(("AWS4" + secret_key).encode("utf-8"), date_stamp)
    region_key = _hmac(date_key, region)
    service_key = _hmac(region_key, SQS_SERVICE)
    return _hmac(service_key, "aws4_request")


def _signed_headers(
    *,
    endpoint: str,
    target: str,
    body: bytes,
    region: str,
    credentials: AwsCredentials,
    now: datetime,
) -> dict[str, str]:
    parsed = parse.urlsplit(endpoint)
    if parsed.scheme != "https" or not parsed.hostname:
        raise SqsTransportError("SQS endpoint must be HTTPS.")
    amz_date = now.astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")
    date_stamp = amz_date[:8]
    headers = {
        "content-type": SQS_CONTENT_TYPE,
        "host": parsed.netloc,
        "x-amz-date": amz_date,
        "x-amz-target": target,
    }
    if credentials.session_token:
        headers["x-amz-security-token"] = credentials.session_token

    signed_header_names = sorted(headers)
    canonical_headers = "".join(f"{name}:{headers[name].strip()}\n" for name in signed_header_names)
    signed_headers = ";".join(signed_header_names)
    payload_hash = hashlib.sha256(body).hexdigest()
    canonical_request = "\n".join(
        [
            "POST",
            parsed.path or "/",
            parsed.query,
            canonical_headers,
            signed_headers,
            payload_hash,
        ]
    )
    credential_scope = f"{date_stamp}/{region}/{SQS_SERVICE}/aws4_request"
    string_to_sign = "\n".join(
        [
            "AWS4-HMAC-SHA256",
            amz_date,
            credential_scope,
            hashlib.sha256(canonical_request.encode("utf-8")).hexdigest(),
        ]
    )
    signature = hmac.new(
        _signing_key(credentials.secret_access_key, date_stamp, region),
        string_to_sign.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    authorization = (
        "AWS4-HMAC-SHA256 "
        f"Credential={credentials.access_key_id}/{credential_scope}, "
        f"SignedHeaders={signed_headers}, Signature={signature}"
    )
    return {
        "Content-Type": SQS_CONTENT_TYPE,
        "Host": parsed.netloc,
        "X-Amz-Date": amz_date,
        "X-Amz-Target": target,
        **(
            {"X-Amz-Security-Token": credentials.session_token}
            if credentials.session_token
            else {}
        ),
        "Authorization": authorization,
    }


@dataclass(frozen=True)
class SqsReceivedMessage:
    message_id: str
    receipt_handle: str
    body: str


class SqsJsonClient:
    """Small SQS JSON-protocol client for the trusted execution controller.

    The project intentionally keeps AWS SDK dependencies out of the FastAPI
    application image. This client supports the exact SQS operations needed by
    the outbox publisher/dispatcher and uses ECS task-role credentials in
    production.
    """

    def __init__(
        self,
        *,
        queue_url: str,
        region: str,
        credentials: AwsCredentials | None = None,
        transport: HttpTransport | None = None,
    ) -> None:
        queue = parse.urlsplit(queue_url)
        if queue.scheme != "https" or not queue.hostname:
            raise SqsTransportError("Queue URL must be an HTTPS SQS URL.")
        self.queue_url = queue_url
        self.region = region
        self.endpoint = f"{queue.scheme}://{queue.netloc}/"
        self.credentials = credentials or AwsCredentials.discover()
        self.transport = transport or UrllibTransport()

    def _call(
        self,
        operation: str,
        payload: dict[str, object],
        *,
        timeout_seconds: float = 10.0,
        now: datetime | None = None,
    ) -> dict[str, object]:
        body = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        target = f"AmazonSQS.{operation}"
        headers = _signed_headers(
            endpoint=self.endpoint,
            target=target,
            body=body,
            region=self.region,
            credentials=self.credentials,
            now=now or datetime.now(UTC),
        )
        raw = self.transport.post(
            self.endpoint,
            headers=headers,
            body=body,
            timeout_seconds=timeout_seconds,
        )
        try:
            decoded = json.loads(raw or b"{}")
        except json.JSONDecodeError as exc:
            raise SqsTransportError("SQS returned malformed JSON.") from exc
        if not isinstance(decoded, dict):
            raise SqsTransportError("SQS returned an invalid response.")
        return {str(key): value for key, value in decoded.items()}

    def send_message(self, body: str) -> str:
        response = self._call(
            "SendMessage",
            {"QueueUrl": self.queue_url, "MessageBody": body},
        )
        message_id = response.get("MessageId")
        if not isinstance(message_id, str) or not message_id:
            raise SqsTransportError("SQS SendMessage response has no MessageId.")
        return message_id

    def receive_messages(
        self,
        *,
        maximum: int = 10,
        wait_seconds: int = 20,
        visibility_timeout: int = 60,
    ) -> list[SqsReceivedMessage]:
        if not 1 <= maximum <= 10:
            raise ValueError("maximum must be between 1 and 10")
        response = self._call(
            "ReceiveMessage",
            {
                "QueueUrl": self.queue_url,
                "MaxNumberOfMessages": maximum,
                "WaitTimeSeconds": wait_seconds,
                "VisibilityTimeout": visibility_timeout,
                "AttributeNames": ["ApproximateReceiveCount", "SentTimestamp"],
            },
            timeout_seconds=float(wait_seconds + 10),
        )
        value = response.get("Messages", [])
        if not isinstance(value, list):
            raise SqsTransportError("SQS ReceiveMessage response is invalid.")
        messages: list[SqsReceivedMessage] = []
        for item in value:
            if not isinstance(item, dict):
                continue
            message_id = item.get("MessageId")
            receipt = item.get("ReceiptHandle")
            body = item.get("Body")
            if all(isinstance(field, str) and field for field in (message_id, receipt, body)):
                messages.append(
                    SqsReceivedMessage(
                        message_id=str(message_id),
                        receipt_handle=str(receipt),
                        body=str(body),
                    )
                )
        return messages

    def delete_message(self, receipt_handle: str) -> None:
        self._call(
            "DeleteMessage",
            {"QueueUrl": self.queue_url, "ReceiptHandle": receipt_handle},
        )

    def change_message_visibility(self, receipt_handle: str, timeout_seconds: int) -> None:
        self._call(
            "ChangeMessageVisibility",
            {
                "QueueUrl": self.queue_url,
                "ReceiptHandle": receipt_handle,
                "VisibilityTimeout": timeout_seconds,
            },
        )


class SqsExecutionQueuePublisher:
    def __init__(self, client: SqsJsonClient) -> None:
        self._client = client

    def publish(self, message: OutboxMessage) -> None:
        self._client.send_message(
            json.dumps(message.payload, separators=(",", ":"), ensure_ascii=False)
        )
