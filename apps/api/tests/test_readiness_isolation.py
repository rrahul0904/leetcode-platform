from __future__ import annotations

from typing import cast

from fastapi.testclient import TestClient
from rigor_api.auth import LocalOIDCProvider
from rigor_api.main import app
from sqlalchemy import Engine, text
from test_async_execution_http import _install_candidate_identity


def test_candidate_readiness_never_includes_another_candidates_mastery(monkeypatch) -> None:
    with TestClient(app) as client:
        engine = cast(Engine, app.state.database_engine)
        provider = cast(LocalOIDCProvider, app.state.local_oidc_provider)

        token_a = provider.issue_test_access_token("candidate", expires_in=900)
        headers_a = {"Authorization": f"Bearer {token_a}"}
        assert client.get("/api/v1/me", headers=headers_a).status_code == 200

        _install_candidate_identity(
            monkeypatch,
            "candidate-readiness-b",
            "local-candidate-readiness-b",
            "candidate-readiness-b@rigor.test",
        )
        token_b = provider.issue_test_access_token("candidate-readiness-b", expires_in=900)
        headers_b = {"Authorization": f"Bearer {token_b}"}
        assert client.get("/api/v1/me", headers=headers_b).status_code == 200

        with engine.begin() as connection:
            candidate_a = connection.execute(
                text("SELECT id FROM users WHERE identity_subject='local-candidate'")
            ).scalar_one()
            candidate_b = connection.execute(
                text(
                    "SELECT id FROM users "
                    "WHERE identity_subject='local-candidate-readiness-b'"
                )
            ).scalar_one()
            competency_id = connection.execute(
                text("SELECT id FROM competencies ORDER BY slug LIMIT 1")
            ).scalar_one()
            connection.execute(
                text(
                    "DELETE FROM candidate_competency_mastery "
                    "WHERE candidate_id IN (:candidate_a, :candidate_b) "
                    "AND competency_id=:competency_id"
                ),
                {
                    "candidate_a": candidate_a,
                    "candidate_b": candidate_b,
                    "competency_id": competency_id,
                },
            )
            connection.execute(
                text(
                    """
                    INSERT INTO candidate_competency_mastery(
                        candidate_id, competency_id, mastery, confidence,
                        evidence_count, last_evidence_at, calculation_version
                    ) VALUES (
                        :candidate_id, :competency_id, 0.91, 0.82,
                        3, CURRENT_TIMESTAMP, 'readiness-isolation-test'
                    )
                    """
                ),
                {"candidate_id": candidate_a, "competency_id": competency_id},
            )

        response_b = client.get("/api/v1/me/readiness", headers=headers_b)
        assert response_b.status_code == 200, response_b.text
        assert response_b.json()["evidence_count"] == 0
        assert response_b.json()["competencies"] == []

        response_a = client.get("/api/v1/me/readiness", headers=headers_a)
        assert response_a.status_code == 200, response_a.text
        assert response_a.json()["evidence_count"] == 3
        assert len(response_a.json()["competencies"]) == 1
        assert response_a.json()["competencies"][0]["score"] == 0.91

        with engine.begin() as connection:
            connection.execute(
                text(
                    "DELETE FROM candidate_competency_mastery "
                    "WHERE candidate_id=:candidate_id AND competency_id=:competency_id"
                ),
                {"candidate_id": candidate_a, "competency_id": competency_id},
            )
