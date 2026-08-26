from __future__ import annotations

import re
from typing import Annotated, Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import text

from .auth import authenticated_principal
from .config import get_settings
from .database import DatabaseEngine, principal_transaction
from .identity_webhooks import WebhookVerificationError, process_clerk_event, verify_svix_webhook
from .object_storage import ObjectStorageConfigurationError, S3Presigner
from .schemas import AuthenticatedPrincipal

router = APIRouter(prefix="/api/v1", tags=["saas"])
MAX_CANDIDATE_FILE_BYTES = 25 * 1024 * 1024


class MeResponse(BaseModel):
    id: UUID
    auth_provider_id: str
    auth_provider: str
    email: str
    email_verified: bool
    display_name: str
    status: str
    roles: list[str]


class PresignUploadRequest(BaseModel):
    file_name: str = Field(min_length=1, max_length=255)
    mime_type: str = Field(min_length=1, max_length=160)
    size_bytes: int = Field(ge=1, le=MAX_CANDIDATE_FILE_BYTES)
    checksum_sha256: str | None = Field(default=None, pattern=r"^[0-9a-fA-F]{64}$")
    category: Literal["resume", "profile_image", "certificate", "other"] = "other"


class PresignUploadResponse(BaseModel):
    file_id: UUID
    method: Literal["PUT"] = "PUT"
    upload_url: str
    expires_seconds: int
    storage_key: str


class DownloadResponse(BaseModel):
    download_url: str
    expires_seconds: int


def _safe_file_name(value: str) -> str:
    leaf = value.replace("\\", "/").rsplit("/", 1)[-1].strip()
    leaf = re.sub(r"[^A-Za-z0-9._ -]+", "_", leaf)
    return (leaf or "upload.bin")[:255]


@router.get("/me", response_model=MeResponse)
def me(
    engine: DatabaseEngine,
    principal: Annotated[AuthenticatedPrincipal, Depends(authenticated_principal)],
) -> MeResponse:
    with principal_transaction(engine, principal) as connection:
        row = connection.execute(
            text(
                """
                SELECT u.id, u.identity_subject, u.auth_provider, u.email,
                       u.email_verified, u.display_name, u.status,
                       COALESCE(
                           array_agg(ur.role_slug)
                           FILTER (WHERE ur.role_slug IS NOT NULL),
                           '{}'
                       ) roles
                FROM users u LEFT JOIN user_roles ur ON ur.user_id=u.id
                WHERE u.identity_subject=:subject
                GROUP BY u.id
                """
            ),
            {"subject": principal.subject_id},
        ).mappings().one()
        return MeResponse(
            id=row["id"],
            auth_provider_id=row["identity_subject"],
            auth_provider=row["auth_provider"],
            email=row["email"],
            email_verified=row["email_verified"],
            display_name=row["display_name"],
            status=row["status"],
            roles=list(row["roles"]),
        )


@router.post("/webhooks/clerk")
async def clerk_webhook(request: Request, engine: DatabaseEngine) -> dict[str, str]:
    settings = get_settings()
    if not settings.clerk_webhook_secret:
        raise HTTPException(status_code=503, detail="Clerk webhook verification is not configured")
    body = await request.body()
    message_id = request.headers.get("svix-id")
    try:
        payload = verify_svix_webhook(
            body=body,
            message_id=message_id,
            timestamp=request.headers.get("svix-timestamp"),
            signatures=request.headers.get("svix-signature"),
            secret=settings.clerk_webhook_secret,
        )
    except WebhookVerificationError as exc:
        raise HTTPException(status_code=401, detail="Invalid Clerk webhook signature") from exc
    if not message_id:
        raise HTTPException(status_code=400, detail="Missing webhook event id")
    try:
        with engine.begin() as connection:
            outcome = process_clerk_event(
                connection,
                external_event_id=message_id,
                payload=payload,
            )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid Clerk webhook payload") from exc
    return {"status": outcome}


@router.post("/files/presign-upload", response_model=PresignUploadResponse)
def presign_upload(
    payload: PresignUploadRequest,
    engine: DatabaseEngine,
    principal: Annotated[AuthenticatedPrincipal, Depends(authenticated_principal)],
) -> PresignUploadResponse:
    settings = get_settings()
    if not settings.s3_upload_bucket:
        raise HTTPException(status_code=503, detail="Private file storage is not configured")
    file_id = uuid4()
    safe_name = _safe_file_name(payload.file_name)
    with principal_transaction(engine, principal) as connection:
        user_id = connection.execute(
            text("SELECT id FROM users WHERE identity_subject=:subject"),
            {"subject": principal.subject_id},
        ).scalar_one()
        storage_key = f"candidates/{user_id}/{file_id}/{safe_name}"
        connection.execute(
            text(
                """
                INSERT INTO candidate_files(
                    id, user_id, storage_key, file_name, mime_type, size_bytes,
                    checksum_sha256, category, status
                ) VALUES (
                    :id, :user_id, :storage_key, :file_name, :mime_type, :size_bytes,
                    :checksum, :category, 'pending_upload'
                )
                """
            ),
            {
                "id": file_id,
                "user_id": user_id,
                "storage_key": storage_key,
                "file_name": safe_name,
                "mime_type": payload.mime_type,
                "size_bytes": payload.size_bytes,
                "checksum": payload.checksum_sha256.lower() if payload.checksum_sha256 else None,
                "category": payload.category,
            },
        )
    try:
        url = S3Presigner.from_environment(
            region=settings.aws_region,
            bucket=settings.s3_upload_bucket,
        ).presign(method="PUT", storage_key=storage_key, expires_seconds=300)
    except ObjectStorageConfigurationError as exc:
        raise HTTPException(
            status_code=503,
            detail="Private file storage is misconfigured",
        ) from exc
    return PresignUploadResponse(
        file_id=file_id,
        upload_url=url,
        expires_seconds=300,
        storage_key=storage_key,
    )


@router.get("/files/{file_id}/download", response_model=DownloadResponse)
def presign_download(
    file_id: UUID,
    engine: DatabaseEngine,
    principal: Annotated[AuthenticatedPrincipal, Depends(authenticated_principal)],
) -> DownloadResponse:
    settings = get_settings()
    if not settings.s3_upload_bucket:
        raise HTTPException(status_code=503, detail="Private file storage is not configured")
    with principal_transaction(engine, principal) as connection:
        storage_key = connection.execute(
            text(
                """
                SELECT storage_key FROM candidate_files
                WHERE id=:file_id AND status IN ('pending_upload', 'available')
                """
            ),
            {"file_id": file_id},
        ).scalar_one_or_none()
    if storage_key is None:
        raise HTTPException(status_code=404, detail="File not found")
    url = S3Presigner.from_environment(
        region=settings.aws_region,
        bucket=settings.s3_upload_bucket,
    ).presign(method="GET", storage_key=storage_key, expires_seconds=300)
    return DownloadResponse(download_url=url, expires_seconds=300)
