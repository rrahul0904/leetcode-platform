"""Two-sided assessment HTTP flow against actual PostgreSQL forced-RLS tables."""

from __future__ import annotations

from uuid import uuid4

import jwt
from fastapi.testclient import TestClient
from rigor_api.auth import LOCAL_IDENTITIES, LocalIdentity, LocalOIDCProvider
from rigor_api.main import app
from rigor_api.schemas import Role
from sqlalchemy import Engine, text


def _headers(provider: LocalOIDCProvider, identity: str, org: str | None = None) -> dict[str, str]:
    raw = provider.issue_test_access_token(identity, expires_in=900)
    if org is not None:
        claims = provider.decode_access_token(raw)
        claims["organization_id"] = org
        raw = jwt.encode(
            claims, provider._private_key, algorithm="RS256", headers={"kid": provider._kid}
        )
    return {"Authorization": f"Bearer {raw}"}


def _identity_id(engine: Engine, subject: str) -> str:
    with engine.connect() as connection:
        value = connection.execute(
            text("SELECT id::text FROM users WHERE identity_subject=:subject"),
            {"subject": subject},
        ).scalar_one()
    return str(value)


def test_employer_assessment_end_to_end_and_cross_tenant_negative(monkeypatch) -> None:
    name = f"separate-candidate-{uuid4().hex[:12]}"
    monkeypatch.setitem(
        LOCAL_IDENTITIES,
        name,
        LocalIdentity(
            subject_id=f"local-{name}",
            email=f"{name}@rigor.test",
            display_name="Separate Candidate",
            roles=(Role.candidate,),
        ),
    )
    with TestClient(app) as client:
        provider: LocalOIDCProvider = app.state.local_oidc_provider
        engine: Engine = app.state.database_engine
        admin_auth = _headers(provider, "platform-administrator")
        reviewer_auth = _headers(provider, "technical-reviewer")
        candidate_auth = _headers(provider, "candidate")
        other_auth = _headers(provider, name)
        for headers in (admin_auth, reviewer_auth, candidate_auth, other_auth):
            response = client.get("/api/v1/me", headers=headers)
            assert response.status_code == 200, response.text

        author_id = _identity_id(engine, "local-platform-administrator")
        reviewer_id = _identity_id(engine, "local-technical-reviewer")
        candidate_id = _identity_id(engine, "local-candidate")

        with engine.begin() as conn:
            org = conn.execute(
                text(
                    """INSERT INTO organizations (name, slug)
                       VALUES ('Assessment Test', :slug) RETURNING id::text"""
                ),
                {"slug": f"assessment-test-{uuid4().hex}"},
            ).scalar_one()
            other_org = conn.execute(
                text(
                    """INSERT INTO organizations (name, slug)
                       VALUES ('Isolated Test', :slug) RETURNING id::text"""
                ),
                {"slug": f"other-assessment-test-{uuid4().hex}"},
            ).scalar_one()
            for user_id, role in ((author_id, "admin"), (reviewer_id, "reviewer")):
                conn.execute(
                    text(
                        """INSERT INTO organization_memberships
                           (organization_id, user_id, role_slug, status)
                           VALUES (:org, :user, :role, 'active')"""
                    ),
                    {"org": org, "user": user_id, "role": role},
                )
            conn.execute(
                text(
                    """INSERT INTO organization_memberships
                       (organization_id, user_id, role_slug, status)
                       VALUES (:org, :user, 'admin', 'active')"""
                ), {"org": other_org, "user": reviewer_id},
            )

        admin_auth = _headers(provider, "platform-administrator", org)
        reviewer_auth = _headers(provider, "technical-reviewer", org)
        wrong_org_auth = _headers(provider, "platform-administrator", other_org)

        unauthorized = client.post(
            "/api/v1/employer/assessments",
            headers=candidate_auth,
            json={"slug": "no-access", "title": "No Access", "duration_minutes": 60,
                  "questions": [{"number": 1, "kind": "written",
                                 "prompt": "Explain SQL join cardinality", "marks": 100}]},
        )
        assert unauthorized.status_code == 403, unauthorized.text

        drafted = client.post(
            "/api/v1/employer/assessments",
            headers=admin_auth,
            json={
                "slug": f"level-four-{uuid4().hex[:10]}",
                "title": "Original Production Data Engineering Screen",
                "duration_minutes": 60,
                "questions": [
                    {"number": 1, "kind": "written", "marks": 60,
                     "prompt": "Explain how to contain a broken production data pipeline safely"},
                    {"number": 2, "kind": "multiple_choice", "marks": 40,
                     "prompt": "Which of these strategies ensures safe idempotent writes?",
                     "options": [
                         "Replay every event without identity",
                         "Use stable partition or event keys",
                         "Use random IDs for every retry",
                         "Remove transaction boundaries",
                     ]},
                ],
            },
        )
        assert drafted.status_code == 201, drafted.text
        assessment = drafted.json()
        aid = assessment["id"]
        assert assessment["status"] == "review_required"
        assert "private_rubric" not in drafted.text
        assert "answer_key" not in drafted.text

        cannot_invite_draft = client.post(
            f"/api/v1/employer/assessments/{aid}/invitations",
            headers=admin_auth,
            json={"candidate_id": candidate_id, "expires_in_hours": 2},
        )
        assert cannot_invite_draft.status_code == 409

        cannot_self_approve = client.post(
            f"/api/v1/employer/assessments/{aid}/publish",
            headers=admin_auth,
            json={
                "rights_evidence": "Original authored employer content confirmed",
                "technical_evidence": "Independent technical review receipt",
                "editorial_evidence": "Independent editorial review receipt",
            },
        )
        assert cannot_self_approve.status_code == 409

        approved = client.post(
            f"/api/v1/employer/assessments/{aid}/publish",
            headers=reviewer_auth,
            json={
                "rights_evidence": "Original authored employer content confirmed",
                "technical_evidence": "Independent technical review receipt",
                "editorial_evidence": "Independent editorial review receipt",
            },
        )
        assert approved.status_code == 200, approved.text
        assert approved.json()["status"] == "published"

        wrong_org = client.get(
            "/api/v1/employer/assessments", headers=wrong_org_auth
        )
        assert wrong_org.status_code == 403

        invite = client.post(
            f"/api/v1/employer/assessments/{aid}/invitations",
            headers=admin_auth,
            json={"candidate_id": candidate_id, "expires_in_hours": 1},
        )
        assert invite.status_code == 201, invite.text
        invitation = invite.json()
        assert len(invitation["acceptance_secret"]) > 32

        listed_invitations = client.get(
            f"/api/v1/employer/assessments/{aid}/invitations",
            headers=admin_auth,
        )
        assert listed_invitations.status_code == 200, listed_invitations.text
        assert invitation["id"] in {entry["id"] for entry in listed_invitations.json()}
        assert "token_digest" not in listed_invitations.text
        assert "acceptance_secret" not in listed_invitations.text

        revoke_target = client.post(
            f"/api/v1/employer/assessments/{aid}/invitations",
            headers=admin_auth,
            json={"candidate_id": candidate_id, "expires_in_hours": 2},
        )
        assert revoke_target.status_code == 201, revoke_target.text
        revoked_invitation = revoke_target.json()
        revoked = client.post(
            f"/api/v1/employer/invitations/{revoked_invitation['id']}/revoke",
            headers=admin_auth,
        )
        assert revoked.status_code == 200, revoked.text
        assert revoked.json()["state"] == "revoked"
        assert "token_digest" not in revoked.text
        assert client.post(
            f"/api/v1/employer/invitations/{revoked_invitation['id']}/revoke",
            headers=admin_auth,
        ).status_code == 409
        revoked_accept = client.post(
            "/api/v1/assessment-invitations/accept",
            headers=candidate_auth,
            json={
                "invitation_id": revoked_invitation["id"],
                "acceptance_secret": revoked_invitation["acceptance_secret"],
            },
        )
        assert revoked_accept.status_code == 409

        cannot_accept_other = client.post(
            "/api/v1/assessment-invitations/accept",
            headers=other_auth,
            json={
                "invitation_id": invitation["id"],
                "acceptance_secret": invitation["acceptance_secret"],
            },
        )
        assert cannot_accept_other.status_code == 404

        accepted = client.post(
            "/api/v1/assessment-invitations/accept",
            headers=candidate_auth,
            json={
                "invitation_id": invitation["id"],
                "acceptance_secret": invitation["acceptance_secret"],
            },
        )
        assert accepted.status_code == 200, accepted.text
        attempt = accepted.json()
        attempt_id = attempt["id"]
        assert attempt["status"] == "in_progress"
        assert len(attempt["questions"]) == 2
        assert "rights_evidence" not in accepted.text
        assert "private_rubric" not in accepted.text
        assert "answer_key" not in accepted.text

        replay = client.post(
            "/api/v1/assessment-invitations/accept",
            headers=candidate_auth,
            json={
                "invitation_id": invitation["id"],
                "acceptance_secret": invitation["acceptance_secret"],
            },
        )
        assert replay.status_code == 409

        other_read = client.get(
            f"/api/v1/assessment-attempts/{attempt_id}", headers=other_auth
        )
        assert other_read.status_code == 404

        saved = client.put(
            f"/api/v1/assessment-attempts/{attempt_id}/responses",
            headers=candidate_auth,
            json={"question_number": 1, "answer_text": "Diagnose, quarantine, repair, validate"},
        )
        assert saved.status_code == 200, saved.text
        assert saved.json()["answers"]["1"] == "Diagnose, quarantine, repair, validate"

        submitted = client.post(
            f"/api/v1/assessment-attempts/{attempt_id}/submit",
            headers=candidate_auth,
        )
        assert submitted.status_code == 200, submitted.text
        assert submitted.json()["status"] == "submitted"
        assert client.put(
            f"/api/v1/assessment-attempts/{attempt_id}/responses",
            headers=candidate_auth,
            json={"question_number": 1, "answer_text": "Change after submit"},
        ).status_code == 409

        listing = client.get(
            f"/api/v1/employer/assessments/{aid}/attempts",
            headers=reviewer_auth,
        )
        assert listing.status_code == 200, listing.text
        assert attempt_id in {a["id"] for a in listing.json()}
        detail = client.get(
            f"/api/v1/employer/attempts/{attempt_id}", headers=reviewer_auth
        )
        assert detail.status_code == 200, detail.text
        assert detail.json()["answers"][0]["answer_text"].startswith("Diagnose")
        assert detail.json()["maximum_marks"] == 100
        assert "answer_key" not in detail.text

        review_payload = {
            "scores": [
                {
                    "question_number": 1, "awarded_marks": 52,
                    "evidence_note": "The candidate identified triage and quarantine.",
                },
                {
                    "question_number": 2, "awarded_marks": 0,
                    "evidence_note": "The candidate did not provide an option.",
                },
            ],
            "overall_notes": "Human rubric review completed with evidence for both items.",
        }
        refused = client.post(
            f"/api/v1/employer/attempts/{attempt_id}/reviews",
            headers=candidate_auth, json=review_payload,
        )
        assert refused.status_code == 403
        reviewed = client.post(
            f"/api/v1/employer/attempts/{attempt_id}/reviews",
            headers=reviewer_auth, json=review_payload,
        )
        assert reviewed.status_code == 201, reviewed.text
        assert reviewed.json()["awarded_marks"] == 52
        assert reviewed.json()["hiring_decision"] is None
        duplicate = client.post(
            f"/api/v1/employer/attempts/{attempt_id}/reviews",
            headers=reviewer_auth, json=review_payload,
        )
        assert duplicate.status_code == 409
        excessive = client.post(
            f"/api/v1/employer/attempts/{attempt_id}/reviews",
            headers=admin_auth,
            json={**review_payload, "scores": [
                {**review_payload["scores"][0], "awarded_marks": 100},
                review_payload["scores"][1],
            ]},
        )
        assert excessive.status_code == 422

