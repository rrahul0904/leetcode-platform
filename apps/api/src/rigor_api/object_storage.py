from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass
from datetime import UTC, datetime
from urllib.parse import quote, urlencode

from .execution_sqs import AwsCredentialProvider, EnvironmentContainerCredentialProvider


class ObjectStorageConfigurationError(RuntimeError):
    pass


def _hmac(key: bytes, value: str) -> bytes:
    return hmac.new(key, value.encode("utf-8"), hashlib.sha256).digest()


def _signing_key(secret: str, date: str, region: str) -> bytes:
    date_key = _hmac(("AWS4" + secret).encode("utf-8"), date)
    region_key = _hmac(date_key, region)
    service_key = _hmac(region_key, "s3")
    return _hmac(service_key, "aws4_request")


@dataclass(frozen=True)
class S3Presigner:
    region: str
    bucket: str
    credential_provider: AwsCredentialProvider

    @classmethod
    def from_environment(cls, *, region: str, bucket: str) -> "S3Presigner":
        if not bucket or "." in bucket or "/" in bucket:
            raise ObjectStorageConfigurationError("A DNS-safe private S3 bucket name is required.")
        return cls(
            region=region,
            bucket=bucket,
            credential_provider=EnvironmentContainerCredentialProvider(),
        )

    def presign(
        self,
        *,
        method: str,
        storage_key: str,
        expires_seconds: int = 300,
        now: datetime | None = None,
    ) -> str:
        if method not in {"GET", "PUT"}:
            raise ValueError("Only GET and PUT may be presigned.")
        if not 1 <= expires_seconds <= 900:
            raise ValueError("Presigned URLs must expire within 1 to 900 seconds.")
        credentials = self.credential_provider.load()
        timestamp = (now or datetime.now(UTC)).astimezone(UTC)
        amz_date = timestamp.strftime("%Y%m%dT%H%M%SZ")
        date_stamp = amz_date[:8]
        host = f"{self.bucket}.s3.{self.region}.amazonaws.com"
        canonical_uri = "/" + quote(storage_key.lstrip("/"), safe="/-_.~")
        scope = f"{date_stamp}/{self.region}/s3/aws4_request"
        params = {
            "X-Amz-Algorithm": "AWS4-HMAC-SHA256",
            "X-Amz-Credential": f"{credentials.access_key_id}/{scope}",
            "X-Amz-Date": amz_date,
            "X-Amz-Expires": str(expires_seconds),
            "X-Amz-SignedHeaders": "host",
        }
        if credentials.session_token:
            params["X-Amz-Security-Token"] = credentials.session_token
        canonical_query = urlencode(sorted(params.items()), quote_via=quote, safe="~")
        canonical_request = "\n".join(
            [method, canonical_uri, canonical_query, f"host:{host}\n", "host", "UNSIGNED-PAYLOAD"]
        )
        string_to_sign = "\n".join(
            [
                "AWS4-HMAC-SHA256",
                amz_date,
                scope,
                hashlib.sha256(canonical_request.encode("utf-8")).hexdigest(),
            ]
        )
        signature = hmac.new(
            _signing_key(credentials.secret_access_key, date_stamp, self.region),
            string_to_sign.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        return f"https://{host}{canonical_uri}?{canonical_query}&X-Amz-Signature={signature}"
