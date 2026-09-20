from __future__ import annotations

from typing import cast

from fastapi.testclient import TestClient
from rigor_api.auth import LocalOIDCProvider
from rigor_api.main import app
from sqlalchemy import Engine, text
from test_async_execution_http import _install_candidate_identity

PROFILE = {
    "target_roles": ["staff backend engineer"],
    "target_companies": ["independent AI company"],
    "experience_level": "senior",
    "preferred_programming_language": "python",
    "weekly_study_hours": 6,
    "interview_date": None,
    "strong_areas": ["python"],
    "weak_areas": ["distributed systems"],
    "preparation_intensity": "focused",
}


def test_candidate_profile_is_self_scoped(monkeypatch) -> None:
    with TestClient(app) as client:
        engine = cast(Engine, app.state.database_engine)
        provider = cast(LocalOIDCProvider, app.state.local_oidc_provider)

        token_a = provider.issue_test_access_token("candidate", expires_in=900)
        headers_a = {"Authorization": f"Bearer {token_a}"}
        saved = client.put("/api/v1/profile", headers=headers_a, json=PROFILE)
        assert saved.status_code == 200, saved.text

        _install_candidate_identity(
            monkeypatch,
            "candidate-profile-b",
            "local-candidate-profile-b",
            "candidate-profile-b@rigor.test",
        )
        token_b = provider.issue_test_access_token("candidate-profile-b", expires_in=900)
        headers_b = {"Authorization": f"Bearer {token_b}"}

        candidate_b = client.get("/api/v1/profile", headers=headers_b)
        assert candidate_b.status_code == 404

        candidate_a = client.get("/api/v1/profile", headers=headers_a)
        assert candidate_a.status_code == 200, candidate_a.text
        assert candidate_a.json()["target_roles"] == PROFILE["target_roles"]

        with engine.begin() as connection:
            user_a = connection.execute(
                text("SELECT id FROM users WHERE identity_subject='local-candidate'")
            ).scalar_one()
            user_b = connection.execute(
                text("SELECT id FROM users WHERE identity_subject='local-candidate-profile-b'")
            ).scalar_one()
            assert connection.execute(
                text("SELECT count(*) FROM candidate_profiles WHERE user_id=:user_id"),
                {"user_id": user_b},
            ).scalar_one() == 0
            connection.execute(
                text("DELETE FROM candidate_profiles WHERE user_id=:user_id"),
                {"user_id": user_a},
            )
