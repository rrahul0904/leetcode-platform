from __future__ import annotations

from typing import cast

from fastapi.testclient import TestClient
from rigor_api.auth import LocalOIDCProvider
from rigor_api.main import app
from sqlalchemy import Engine, text


def cleanup_local_candidate(engine: Engine) -> None:
    with engine.begin() as connection:
        user_id = connection.execute(
            text("SELECT id FROM users WHERE identity_subject = 'local-candidate'")
        ).scalar_one_or_none()
        if user_id:
            connection.execute(
                text("DELETE FROM audit_events WHERE actor_user_id = :user_id"),
                {"user_id": user_id},
            )
            connection.execute(text("DELETE FROM users WHERE id = :user_id"), {"user_id": user_id})


def test_candidate_onboarding_save_resume_edit_and_audit() -> None:
    with TestClient(app) as client:
        engine = cast(Engine, app.state.database_engine)
        provider = cast(LocalOIDCProvider, app.state.local_oidc_provider)
        cleanup_local_candidate(engine)
        token = provider.issue_test_access_token("candidate", expires_in=900)
        headers = {"Authorization": f"Bearer {token}"}

        empty = client.get("/api/v1/profile", headers=headers)
        assert empty.status_code == 404

        payload = {
            "target_roles": ["staff backend engineer"],
            "target_companies": ["independent large AI lab"],
            "experience_level": "senior",
            "preferred_programming_language": "python",
            "weekly_study_hours": 7,
            "interview_date": None,
            "strong_areas": ["python"],
            "weak_areas": ["distributed systems"],
            "preparation_intensity": "focused",
        }
        saved = client.put("/api/v1/profile", headers=headers, json=payload)
        assert saved.status_code == 200
        assert saved.json()["completion_state"] == "complete"
        assert saved.json()["weekly_study_hours"] == 7

        resumed = client.get("/api/v1/profile", headers=headers)
        assert resumed.status_code == 200
        assert resumed.json()["target_roles"] == ["staff backend engineer"]

        payload["weekly_study_hours"] = 9
        edited = client.put("/api/v1/profile", headers=headers, json=payload)
        assert edited.status_code == 200
        assert edited.json()["weekly_study_hours"] == 9

        with engine.begin() as connection:
            assert (
                connection.execute(
                    text(
                        """
                        SELECT count(*) FROM audit_events a
                        JOIN users u ON u.id = a.actor_user_id
                        WHERE u.identity_subject = 'local-candidate'
                          AND a.action = 'profile.saved'
                        """
                    )
                ).scalar_one()
                == 2
            )
            assert (
                connection.execute(
                    text(
                        """
                        SELECT role_slug FROM user_roles r
                        JOIN users u ON u.id = r.user_id
                        WHERE u.identity_subject = 'local-candidate'
                        """
                    )
                ).scalar_one()
                == "candidate"
            )
        cleanup_local_candidate(engine)


def test_profile_validation_and_forbidden_role() -> None:
    with TestClient(app) as client:
        provider = cast(LocalOIDCProvider, app.state.local_oidc_provider)
        candidate = provider.issue_test_access_token("candidate", expires_in=900)
        invalid = client.put(
            "/api/v1/profile",
            headers={"Authorization": f"Bearer {candidate}"},
            json={
                "target_roles": [],
                "experience_level": "intern",
                "preferred_programming_language": "javascript",
                "weekly_study_hours": 0,
                "preparation_intensity": "extreme",
            },
        )
        assert invalid.status_code == 422
        assert invalid.json()["code"] == "request_validation_failed"

        author = provider.issue_test_access_token("author", expires_in=900)
        forbidden = client.get("/api/v1/profile", headers={"Authorization": f"Bearer {author}"})
        assert forbidden.status_code == 403
        assert forbidden.json()["code"] == "forbidden"
