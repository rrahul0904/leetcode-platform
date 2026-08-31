from __future__ import annotations

from datetime import UTC, datetime
from typing import cast

from fastapi.testclient import TestClient
from rigor_api.auth import LocalOIDCProvider
from rigor_api.main import app
from rigor_api.profiles import ProfileRepository
from rigor_api.schemas import (
    AuthenticatedPrincipal,
    CandidateProfileInput,
    Role,
)
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


def test_external_profile_write_never_rewrites_database_role() -> None:
    subject = "clerk-profile-role-regression"
    now = datetime.now(UTC)
    principal = AuthenticatedPrincipal(
        subject_id=subject,
        email="profile-role-regression@example.test",
        display_name="Profile Role Regression",
        # Deliberately conflict with the persisted authorization state. A profile
        # repository call must never use this request claim to rewrite user_roles.
        roles=[Role.candidate],
        permissions=[],
        authentication_provider="clerk",
        token_issued_at=now,
        correlation_id="profile-role-regression",
    )
    profile = CandidateProfileInput(
        target_roles=["principal engineer"],
        target_companies=[],
        experience_level="principal",
        preferred_programming_language="python",
        weekly_study_hours=5,
        interview_date=None,
        strong_areas=["architecture"],
        weak_areas=["sql"],
        preparation_intensity="focused",
    )

    with TestClient(app):
        engine = cast(Engine, app.state.database_engine)
        with engine.begin() as connection:
            user_id = connection.execute(
                text(
                    """
                    INSERT INTO users(
                        identity_subject, email, display_name, email_verified,
                        auth_provider, status
                    ) VALUES (
                        :subject, :email, :display_name, true, 'clerk', 'active'
                    )
                    ON CONFLICT (identity_subject) DO UPDATE SET email=EXCLUDED.email
                    RETURNING id
                    """
                ),
                {
                    "subject": subject,
                    "email": principal.email,
                    "display_name": principal.display_name,
                },
            ).scalar_one()
            connection.execute(
                text("DELETE FROM user_roles WHERE user_id=:user_id"), {"user_id": user_id}
            )
            connection.execute(
                text("INSERT INTO user_roles(user_id, role_slug) VALUES (:user_id, :role)"),
                {"user_id": user_id, "role": Role.platform_administrator.value},
            )

        ProfileRepository(engine).put(principal, profile)

        with engine.begin() as connection:
            roles = connection.execute(
                text(
                    """
                    SELECT role_slug FROM user_roles r
                    JOIN users u ON u.id=r.user_id
                    WHERE u.identity_subject=:subject
                    ORDER BY role_slug
                    """
                ),
                {"subject": subject},
            ).scalars().all()
            assert roles == [Role.platform_administrator.value]
            user_id = connection.execute(
                text("SELECT id FROM users WHERE identity_subject=:subject"),
                {"subject": subject},
            ).scalar_one()
            connection.execute(
                text("DELETE FROM audit_events WHERE actor_user_id=:user_id"),
                {"user_id": user_id},
            )
            connection.execute(
                text("DELETE FROM candidate_profiles WHERE user_id=:user_id"),
                {"user_id": user_id},
            )
            connection.execute(
                text("DELETE FROM user_roles WHERE user_id=:user_id"),
                {"user_id": user_id},
            )
            connection.execute(
                text("DELETE FROM users WHERE id=:user_id"),
                {"user_id": user_id},
            )
