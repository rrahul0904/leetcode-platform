from __future__ import annotations

import hashlib
import hmac
import ipaddress
import json
import os
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Protocol
from urllib import error, parse, request

from .outbox import OutboxMessage

SQS_CONTENT_TYPE = "application/x-amz-json-1.0"
SQS_SERVICE = "sqs"
MAX_CREDENTIAL_RESPONSE_BYTES = 32 * 1024
CREDENTIAL_REFRESH_SKEW = timedelta(minutes=5)


class SqsTransportError(RuntimeError):
    pass


@dataclass(frozen=True)
class AwsCredentials:
    access_key_id: str
    secret_access_key: str
    session_token: str | None = None
    expires_at: datetime | None = None


class AwsCredentialProvider(Protocol):
    def load(self) -> AwsCredentials: ...


@dataclass(frozen=True)
class StaticCredentialProvider:
    credentials: AwsCredentials

    def load(self) -> AwsCredentials:
        return self.credentials


def _container_endpoint_allowed(url: str) -> bool:
    parsed = parse.urlsplit(url)
    if parsed.scheme != "http" or not parsed.hostname:
        return False
    if parsed.hostname == "localhost":
        return True
    try:
        address = ipaddress.ip_address(parsed.hostname)
    except ValueError:
        return False
    return address.is_loopback or address.is_link_local


def _container_authorization_header() -> str | None:
    direct = os.getenv("AWS_CONTAINER_AUTHORIZATION_TOKEN")
    if direct:
        return direct.strip()
    token_file = os.getenv("AWS_CONTAINER_AUTHORIZATION_TOKEN_FILE")
    if not token_file:
        return None
    try:
        return Path(token_file).read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise SqsTransportError("Container credential authorization token is unavailable.") from exc


def _parse_expiration(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise SqsTransportError("Container credential expiration is invalid.") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise SqsTransportError("Container credential expiration must include a timezone.")
    return parsed.astimezone(UTC)


class EnvironmentContainerCredentialProvider:
    """Refreshable credential provider for trusted ECS/EKS controller workloads."""

    def __init__(self) -> None:
        self._cached: AwsCredentials | None = None

    def load(self) -> AwsCredentials:
        env_access_key = os.getenv("AWS_ACCESS_KEY_ID")
        env_secret_key = os.getenv("AWS_SECRET_ACCESS_KEY")
        if env_access_key and env_secret_key:
            return AwsCredentials(
                access_key_id=env_access_key,
                secret_access_key=env_secret_key,
                session_token=os.getenv("AWS_SESSION_TOKEN"),
            )

        now = datetime.now(UTC)
        if self._cached is not None:
            expires_at = self._cached.expires_at
            if expires_at is None or expires_at - CREDENTIAL_REFRESH_SKEW > now:
                return self._cached

        self._cached = self._load_container_credentials()
        return self._cached

    @staticmethod
    def _load_container_credentials() -> AwsCredentials:
        relative_uri = os.getenv("AWS_CONTAINER_CREDENTIALS_RELATIVE_URI")
        full_uri = os.getenv("AWS_CONTAINER_CREDENTIALS_FULL_URI")
        if relative_uri:
            credential_url = f"http://169.254.170.2{relative_uri}"
        elif full_uri:
            credential_url = full_uri
        else:
            raise SqsTransportError(
                "AWS task or pod credentials are unavailable to the trusted controller."
            )
        if not _container_endpoint_allowed(credential_url):
            raise SqsTransportError("Untrusted container credential endpoint configuration.")

        headers: dict[str, str] = {"Accept": "application/json"}
        authorization = _container_authorization_header()
        if authorization:
            headers["Authorization"] = authorization
        credential_request = request.Request(credential_url, headers=headers, method="GET")
        try:
            with request.urlopen(credential_request, timeout=2.0) as response:
                raw = response.read(MAX_CREDENTIAL_RESPONSE_BYTES)
        except OSError as exc:
            raise SqsTransportError("Unable to load task or pod credentials.") from exc
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise SqsTransportError("Container credential response is malformed.") from exc
        if not isinstance(payload, dict):
            raise SqsTransportError("Container credential response is invalid.")
        access_key = payload.get("AccessKeyId")
        secret_key = payload.get("SecretAccessKey")
        token = payload.get("Token")
        if not isinstance(access_key, str) or not isinstance(secret_key, str):
            raise SqsTransportError("Container credential response is incomplete.")
        return AwsCredentials(
            access_key_id=access_key,
            secret_access_key=secret_key,
            session_token=str(token) if token else None,
            expires_at=_parse_expiration(payload.get("Expiration")),
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
    canonical_headers_map = {
        "content-type": SQS_CONTENT_TYPE,
        "host": parsed.netloc,
        "x-amz-date": amz_date,
        "x-amz-target": target,
    }
    if credentials.session_token:
        canonical_headers_map["x-amz-security-token"] = credentials.session_token

    names = sorted(canonical_headers_map)
    canonical_headers = "".join(
        f"{name}:{canonical_headers_map[name].strip()}\n" for name in names
    )
    signed_headers = ";".join(names)
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
    """Minimal refreshable SQS JSON-protocol client for trusted execution workers."""

    def __init__(
        self,
        *,
        queue_url: str,
        region: str,
        credentials: AwsCredentials | None = None,
        credential_provider: AwsCredentialProvider | None = None,
        transport: HttpTransport | None = None,
    ) -> None:
        queue = parse.urlsplit(queue_url)
        if queue.scheme != "https" or not queue.hostname:
            raise SqsTransportError("Queue URL must be an HTTPS SQS URL.")
        if credentials is not None and credential_provider is not None:
            raise ValueError("Provide credentials or a credential provider, not both.")
        self.queue_url = queue_url
        self.region = region
        self.endpoint = f"{queue.scheme}://{queue.netloc}/"
        self.credential_provider = credential_provider or (
            StaticCredentialProvider(credentials)
            if credentials is not None
            else EnvironmentContainerCredentialProvider()
        )
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
            credentials=self.credential_provider.load(),
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
