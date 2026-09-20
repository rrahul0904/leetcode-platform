from __future__ import annotations

from types import SimpleNamespace
from typing import cast
from unittest.mock import MagicMock

from fastapi.testclient import TestClient
from rigor_api import saas_routes
from rigor_api.auth import LocalOIDCProvider
from rigor_api.main import app
from sqlalchemy import Engine, text
from test_async_execution_http import _install_candidate_identity


def test_candidate_cannot_presign_another_candidates_private_file(monkeypatch) -> None:
    settings = SimpleNamespace(
        s3_upload_bucket="skillforge-private-test",
        aws_region="us-east-1",
    )
    signer = MagicMock()
    signer.presign.return_value = "https://private-storage.example.test/signed"
    monkeypatch.setattr(saas_routes, "get_settings", lambda: settings)
    monkeypatch.setattr(
        saas_routes.S3Presigner,
        "from_environment",
        lambda **_kwargs: signer,
    )

    with TestClient(app) as client:
        engine = cast(Engine, app.state.database_engine)
        provider = cast(LocalOIDCProvider, app.state.local_oidc_provider)

        token_a = provider.issue_test_access_token("candidate", expires_in=900)
        headers_a = {"Authorization": f"Bearer {token_a}"}
        created = client.post(
            "/api/v1/files/presign-upload",
            headers=headers_a,
            json={
                "file_name": "resume.pdf",
                "mime_type": "application/pdf",
                "size_bytes": 128,
                "category": "resume",
            },
        )
        assert created.status_code == 200, created.text
        file_id = created.json()["file_id"]

        _install_candidate_identity(
            monkeypatch,
            "candidate-private-file-b",
            "local-candidate-private-file-b",
            "candidate-private-file-b@rigor.test",
        )
        token_b = provider.issue_test_access_token("candidate-private-file-b", expires_in=900)
        headers_b = {"Authorization": f"Bearer {token_b}"}

        denied = client.get(f"/api/v1/files/{file_id}/download", headers=headers_b)
        assert denied.status_code == 404

        owner = client.get(f"/api/v1/files/{file_id}/download", headers=headers_a)
        assert owner.status_code == 200, owner.text
        assert owner.json()["download_url"] == "https://private-storage.example.test/signed"

        with engine.begin() as connection:
            persisted_owner = connection.execute(
                text(
                    """
                    SELECT u.identity_subject
                    FROM candidate_files f
                    JOIN users u ON u.id=f.user_id
                    WHERE f.id=:file_id
                    """
                ),
                {"file_id": file_id},
            ).scalar_one()
            assert persisted_owner == "local-candidate"
            connection.execute(
                text("DELETE FROM candidate_files WHERE id=:file_id"),
                {"file_id": file_id},
            )
