from __future__ import annotations

from typing import cast

from fastapi.testclient import TestClient
from rigor_api.auth import LocalOIDCProvider
from rigor_api.main import app


def test_question_intelligence_inventory_and_idempotent_gap_recompute() -> None:
    with TestClient(app) as client:
        provider = cast(LocalOIDCProvider, app.state.local_oidc_provider)
        administrator = provider.issue_test_access_token("platform-administrator", expires_in=900)
        candidate = provider.issue_test_access_token("candidate", expires_in=900)
        admin_headers = {"Authorization": f"Bearer {administrator}"}
        candidate_headers = {"Authorization": f"Bearer {candidate}"}

        for path in (
            "/api/v1/admin/questions",
            "/api/v1/admin/questions/duplicates",
            "/api/v1/admin/questions/families",
            "/api/v1/admin/questions/gaps",
            "/api/v1/admin/questions/freshness",
            "/api/v1/admin/questions/licenses",
            "/api/v1/admin/questions/provenance",
        ):
            assert client.get(path, headers=candidate_headers).status_code == 403
            response = client.get(path, headers=admin_headers)
            assert response.status_code == 200
            assert isinstance(response.json(), list)

        first = client.post("/api/v1/admin/questions/gaps/recompute", headers=admin_headers)
        assert first.status_code == 200
        assert first.json()["open_gap_count"] >= 1

        second = client.post("/api/v1/admin/questions/gaps/recompute", headers=admin_headers)
        assert second.status_code == 200
        assert second.json()["created_count"] == 0
        assert second.json()["open_gap_count"] == first.json()["open_gap_count"]

        gaps = client.get("/api/v1/admin/questions/gaps", headers=admin_headers)
        assert gaps.status_code == 200
        assert len(gaps.json()) >= first.json()["open_gap_count"]
        assert all(gap["recommended_question_count"] > 0 for gap in gaps.json())
