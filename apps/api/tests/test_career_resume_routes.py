from __future__ import annotations

import hashlib
from io import BytesIO
from types import SimpleNamespace
from typing import cast
from zipfile import ZIP_DEFLATED, ZipFile

from fastapi.testclient import TestClient
from rigor_api import career_resume_routes, saas_routes
from rigor_api.auth import LOCAL_IDENTITIES, LocalIdentity, LocalOIDCProvider
from rigor_api.main import app
from rigor_api.schemas import Role
from sqlalchemy import Engine, text

SECOND_IDENTITY_KEY = "resume-candidate-b"
SECOND_SUBJECT = "local-resume-candidate-b"
DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


class FakePresigner:
    @classmethod
    def from_environment(cls, *, region: str, bucket: str) -> FakePresigner:
        assert region == "us-east-1"
        assert bucket == "test-resume-bucket"
        return cls()

    def presign(self, *, method: str, storage_key: str, expires_seconds: int) -> str:
        assert method in {"GET", "PUT"}
        assert storage_key.startswith("candidates/")
        assert 1 <= expires_seconds <= 300
        return f"https://example.invalid/{method.casefold()}/{storage_key}"


def docx_bytes() -> bytes:
    text_value = (
        "Senior backend engineer with Python, PostgreSQL, Docker, AWS, system design, and "
        "measurable production platform ownership."
    )
    document = f"""<?xml version="1.0" encoding="UTF-8"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body><w:p><w:r><w:t>{text_value}</w:t></w:r></w:p></w:body>
</w:document>
""".encode()
    buffer = BytesIO()
    with ZipFile(buffer, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr(
            "[Content_Types].xml",
            b"<Types xmlns='http://schemas.openxmlformats.org/package/2006/content-types'/>",
        )
        archive.writestr("word/document.xml", document)
    return buffer.getvalue()


def cleanup_candidate(engine: Engine, subject: str) -> None:
    with engine.begin() as connection:
        user_id = connection.execute(
            text("SELECT id FROM users WHERE identity_subject=:subject"),
            {"subject": subject},
        ).scalar_one_or_none()
        if user_id is not None:
            connection.execute(
                text("DELETE FROM audit_events WHERE actor_user_id=:user_id"),
                {"user_id": user_id},
            )
            connection.execute(text("DELETE FROM users WHERE id=:user_id"), {"user_id": user_id})


def install_second_candidate() -> None:
    LOCAL_IDENTITIES[SECOND_IDENTITY_KEY] = LocalIdentity(
        SECOND_SUBJECT,
        "resume-candidate-b@rigor.test",
        "Resume Candidate B",
        (Role.candidate,),
    )


def test_resume_extraction_is_idempotent_and_candidate_owned(monkeypatch) -> None:
    settings = SimpleNamespace(s3_upload_bucket="test-resume-bucket", aws_region="us-east-1")
    monkeypatch.setattr(saas_routes, "get_settings", lambda: settings)
    monkeypatch.setattr(career_resume_routes, "get_settings", lambda: settings)
    monkeypatch.setattr(saas_routes, "S3Presigner", FakePresigner)
    monkeypatch.setattr(career_resume_routes, "S3Presigner", FakePresigner)

    data = docx_bytes()
    monkeypatch.setattr(career_resume_routes, "_download_resume_bytes", lambda _url: data)

    with TestClient(app) as client:
        engine = cast(Engine, app.state.database_engine)
        provider = cast(LocalOIDCProvider, app.state.local_oidc_provider)
        cleanup_candidate(engine, "local-candidate")
        cleanup_candidate(engine, SECOND_SUBJECT)
        install_second_candidate()
        try:
            token_a = provider.issue_test_access_token("candidate", expires_in=900)
            token_b = provider.issue_test_access_token(SECOND_IDENTITY_KEY, expires_in=900)
            headers_a = {"Authorization": f"Bearer {token_a}"}
            headers_b = {"Authorization": f"Bearer {token_b}"}

            presigned = client.post(
                "/api/v1/files/presign-upload",
                headers=headers_a,
                json={
                    "file_name": "resume.docx",
                    "mime_type": DOCX_MIME,
                    "size_bytes": len(data),
                    "checksum_sha256": hashlib.sha256(data).hexdigest(),
                    "category": "resume",
                },
            )
            assert presigned.status_code == 200
            file_id = presigned.json()["file_id"]

            extracted = client.post(
                f"/api/v1/career/resumes/{file_id}/extract",
                headers=headers_a,
            )
            assert extracted.status_code == 200
            body = extracted.json()
            assert body["candidate_file_id"] == file_id
            assert body["extraction_method"] == "docx_xml"
            assert body["character_count"] >= 40

            again = client.post(
                f"/api/v1/career/resumes/{file_id}/extract",
                headers=headers_a,
            )
            assert again.status_code == 200
            assert again.json()["document_id"] == body["document_id"]

            foreign = client.post(
                f"/api/v1/career/resumes/{file_id}/extract",
                headers=headers_b,
            )
            assert foreign.status_code == 404

            analysis = client.post(
                "/api/v1/career/jobs/analyze",
                headers=headers_a,
                json={
                    "document_id": body["document_id"],
                    "job_title": "Backend Engineer",
                    "company": "Example Co",
                    "job_description": (
                        "Backend engineer role requiring Python, PostgreSQL, Docker, AWS, "
                        "Kubernetes and system design for reliable production services."
                    ),
                },
            )
            assert analysis.status_code == 200
            assert analysis.json()["document_id"] == body["document_id"]
        finally:
            LOCAL_IDENTITIES.pop(SECOND_IDENTITY_KEY, None)
            cleanup_candidate(engine, "local-candidate")
            cleanup_candidate(engine, SECOND_SUBJECT)


def test_checksum_mismatch_quarantines_resume(monkeypatch) -> None:
    settings = SimpleNamespace(s3_upload_bucket="test-resume-bucket", aws_region="us-east-1")
    monkeypatch.setattr(saas_routes, "get_settings", lambda: settings)
    monkeypatch.setattr(career_resume_routes, "get_settings", lambda: settings)
    monkeypatch.setattr(saas_routes, "S3Presigner", FakePresigner)
    monkeypatch.setattr(career_resume_routes, "S3Presigner", FakePresigner)

    data = docx_bytes()
    monkeypatch.setattr(career_resume_routes, "_download_resume_bytes", lambda _url: data)

    with TestClient(app) as client:
        engine = cast(Engine, app.state.database_engine)
        provider = cast(LocalOIDCProvider, app.state.local_oidc_provider)
        cleanup_candidate(engine, "local-candidate")
        try:
            token = provider.issue_test_access_token("candidate", expires_in=900)
            headers = {"Authorization": f"Bearer {token}"}
            presigned = client.post(
                "/api/v1/files/presign-upload",
                headers=headers,
                json={
                    "file_name": "resume.docx",
                    "mime_type": DOCX_MIME,
                    "size_bytes": len(data),
                    "checksum_sha256": "0" * 64,
                    "category": "resume",
                },
            )
            assert presigned.status_code == 200
            file_id = presigned.json()["file_id"]

            rejected = client.post(
                f"/api/v1/career/resumes/{file_id}/extract",
                headers=headers,
            )
            assert rejected.status_code == 422
            assert "checksum" in rejected.json()["detail"].casefold()

            quarantined = client.post(
                f"/api/v1/career/resumes/{file_id}/extract",
                headers=headers,
            )
            assert quarantined.status_code == 409
            assert "quarantined" in quarantined.json()["detail"].casefold()
        finally:
            cleanup_candidate(engine, "local-candidate")
