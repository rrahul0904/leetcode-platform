"""Authenticated employer signup, membership selection and tenant isolation."""

from __future__ import annotations

from typing import cast
from uuid import uuid4

from fastapi.testclient import TestClient
from rigor_api.auth import LOCAL_IDENTITIES, LocalIdentity, LocalOIDCProvider
from rigor_api.main import app
from rigor_api.schemas import Role
from sqlalchemy import Engine, text


def test_self_service_employer_onboarding_and_member_authorization(monkeypatch) -> None:
    suffix = uuid4().hex[:12]
    owner_key = "employer-owner-" + suffix
    reviewer_key = "employer-reviewer-" + suffix
    for key in (owner_key, reviewer_key):
        monkeypatch.setitem(
            LOCAL_IDENTITIES,
            key,
            LocalIdentity(
                subject_id="local-" + key,
                email=key + "@rigor.test",
                display_name=key,
                roles=(Role.candidate,),
            ),
        )
    with TestClient(app) as client:
        provider = cast(LocalOIDCProvider, app.state.local_oidc_provider)
        engine = cast(Engine, app.state.database_engine)
        owner = {
            "Authorization": "Bearer "
            + provider.issue_test_access_token(owner_key, expires_in=900)
        }
        reviewer = {
            "Authorization": "Bearer "
            + provider.issue_test_access_token(reviewer_key, expires_in=900)
        }
        for auth in (owner, reviewer):
            assert client.get("/api/v1/me", headers=auth).status_code == 200

        unique_slug = "assessment-org-" + uuid4().hex
        created = client.post(
            "/api/v1/employer/organizations",
            headers=owner,
            json={"name": "REAs Quality Engineering", "slug": unique_slug},
        )
        assert created.status_code == 201, created.text
        organization = created.json()
        org_id = organization["id"]
        assert organization["membership_role"] == "owner"

        own_listing = client.get("/api/v1/employer/organizations", headers=owner)
        assert own_listing.status_code == 200
        assert org_id in {row["id"] for row in own_listing.json()}

        no_selection = client.get("/api/v1/employer/assessments", headers=owner)
        assert no_selection.status_code == 403
        with_selection = {
            **owner, "X-Rigor-Organization-ID": org_id,
        }
        success = client.get("/api/v1/employer/assessments", headers=with_selection)
        assert success.status_code == 200, success.text

        forbidden_other_org = client.get(
            "/api/v1/employer/assessments",
            headers={**reviewer, "X-Rigor-Organization-ID": org_id},
        )
        assert forbidden_other_org.status_code in (401, 403)

        with engine.connect() as conn:
            user_id = conn.execute(
                text(
                    "SELECT id::text FROM users "
                    "WHERE identity_subject=:subject"
                ),
                {"subject": "local-" + reviewer_key},
            ).scalar_one()

        member_added = client.post(
            f"/api/v1/employer/organizations/{org_id}/members",
            headers=with_selection,
            json={"user_id": user_id, "role": "reviewer"},
        )
        assert member_added.status_code == 201, member_added.text
        assert member_added.json()["role"] == "reviewer"

        reviewer_selected = {
            **reviewer, "X-Rigor-Organization-ID": org_id,
        }
        reviewer_sees_workspace = client.get(
            "/api/v1/employer/assessments", headers=reviewer_selected
        )
        assert reviewer_sees_workspace.status_code == 200

        reviewer_cannot_add_admins = client.post(
            f"/api/v1/employer/organizations/{org_id}/members",
            headers=reviewer_selected,
            json={"user_id": user_id, "role": "admin"},
        )
        assert reviewer_cannot_add_admins.status_code == 403

        second_attempt = client.post(
            f"/api/v1/employer/organizations/{org_id}/members",
            headers=with_selection,
            json={"user_id": user_id, "role": "reviewer"},
        )
        assert second_attempt.status_code == 409
