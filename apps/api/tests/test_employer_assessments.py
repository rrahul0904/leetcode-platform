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

        no_key_approval = client.post(
            f"/api/v1/employer/assessments/{aid}/publish",
            headers=reviewer_auth,
            json={
                "rights_evidence": "Original authored employer content confirmed",
                "technical_evidence": "Independent technical review receipt",
                "editorial_evidence": "Independent editorial review receipt",
            },
        )
        assert no_key_approval.status_code == 409
        saved_secret_key = client.put(
            f"/api/v1/employer/assessments/{aid}/private-key",
            headers=admin_auth,
            json={
                "mcq_answers": {"2": "B"},
                "reviewer_guidance": "Human reviewers should evaluate the pipeline recovery logic.",
            },
        )
        assert saved_secret_key.status_code == 200, saved_secret_key.text
        reviewer_private_key = client.get(
            f"/api/v1/employer/assessments/{aid}/private-key",
            headers=reviewer_auth,
        )
        assert reviewer_private_key.status_code == 200, reviewer_private_key.text
        assert reviewer_private_key.json()["mcq_answers"]["2"] == "B"
        candidate_private_key = client.get(
            f"/api/v1/employer/assessments/{aid}/private-key",
            headers=candidate_auth,
        )
        assert candidate_private_key.status_code == 403

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

        reviewer_second_org = _headers(provider, "technical-reviewer", other_org)
        isolated_listing = client.get(
            "/api/v1/employer/assessments", headers=reviewer_second_org
        )
        assert isolated_listing.status_code == 200, isolated_listing.text
        assert aid not in {item["id"] for item in isolated_listing.json()}
        isolated_invite = client.post(
            f"/api/v1/employer/assessments/{aid}/invitations",
            headers=reviewer_second_org,
            json={"candidate_id": candidate_id, "expires_in_hours": 1},
        )
        assert isolated_invite.status_code == 404

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

        own_history = client.get("/api/v1/assessment-attempts", headers=candidate_auth)
        assert own_history.status_code == 200, own_history.text
        assert attempt_id in {item["id"] for item in own_history.json()}
        other_history = client.get("/api/v1/assessment-attempts", headers=other_auth)
        assert other_history.status_code == 200
        assert attempt_id not in {item["id"] for item in other_history.json()}

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

        # Clearing an earlier answer is a deliberate, persistent operation;
        # candidates must not be trapped by an unsaved blank draft.
        cleared = client.put(
            f"/api/v1/assessment-attempts/{attempt_id}/responses",
            headers=candidate_auth,
            json={"question_number": 1, "answer_text": ""},
        )
        assert cleared.status_code == 200, cleared.text
        assert cleared.json()["answers"]["1"] == ""
        restored_answer = client.put(
            f"/api/v1/assessment-attempts/{attempt_id}/responses",
            headers=candidate_auth,
            json={"question_number": 1, "answer_text":
                  "Diagnose, quarantine, repair, validate"},
        )
        assert restored_answer.status_code == 200, restored_answer.text


        no_consent = client.get(
            f"/api/v1/assessment-attempts/{attempt_id}/ai-interview",
            headers=candidate_auth,
        )
        assert no_consent.status_code == 404
        refused_consent = client.post(
            f"/api/v1/assessment-attempts/{attempt_id}/ai-interview/consent",
            headers=candidate_auth,
            json={"agree_to_ai_processing": False},
        )
        assert refused_consent.status_code == 422
        consent = client.post(
            f"/api/v1/assessment-attempts/{attempt_id}/ai-interview/consent",
            headers=candidate_auth,
            json={"agree_to_ai_processing": True},
        )
        assert consent.status_code == 200, consent.text
        assert consent.json()["status"] == "active"
        assert client.get(
            f"/api/v1/assessment-attempts/{attempt_id}/ai-interview",
            headers=other_auth,
        ).status_code == 404

        class FakeInterviewProvider:
            def followup(self, prompt):
                assert len(prompt.questions) == 2
                assert "private_rubric" not in str(prompt)
                assert "reviewer_guidance" not in str(prompt)
                assert "Correct answer" not in str(prompt)
                return "How would you safely replay failed events without duplicates?"

        monkeypatch.setattr(
            "rigor_api.employer_ai_interview_routes.employer_interview_provider",
            lambda: FakeInterviewProvider(),
        )
        request_id = "interview-test-" + uuid4().hex
        turn = client.post(
            f"/api/v1/assessment-attempts/{attempt_id}/ai-interview/messages",
            headers=candidate_auth,
            json={"message": "I will quarantine bad events and add idempotency keys",
                  "request_id": request_id},
        )
        assert turn.status_code == 200, turn.text
        assert turn.json()["turn_count"] == 1
        assert len(turn.json()["messages"]) == 2
        assert turn.json()["messages"][-1]["role"] == "interviewer"

        replay_turn = client.post(
            f"/api/v1/assessment-attempts/{attempt_id}/ai-interview/messages",
            headers=candidate_auth,
            json={"message": "I will quarantine bad events and add idempotency keys",
                  "request_id": request_id},
        )
        assert replay_turn.status_code == 200
        assert len(replay_turn.json()["messages"]) == 2
        mismatched_turn = client.post(
            f"/api/v1/assessment-attempts/{attempt_id}/ai-interview/messages",
            headers=candidate_auth,
            json={"message": "Replace all previous candidate messages",
                  "request_id": request_id},
        )
        assert mismatched_turn.status_code == 409
        withdrawn = client.post(
            f"/api/v1/assessment-attempts/{attempt_id}/ai-interview/withdraw",
            headers=candidate_auth,
        )
        assert withdrawn.status_code == 200
        assert withdrawn.json()["status"] == "withdrawn"
        assert client.post(
            f"/api/v1/assessment-attempts/{attempt_id}/ai-interview/messages",
            headers=candidate_auth,
            json={"message": "Continue after withdrawing my consent",
                  "request_id": "withdrawn-" + uuid4().hex},
        ).status_code == 409
        assert client.post(
            f"/api/v1/assessment-attempts/{attempt_id}/ai-interview/consent",
            headers=candidate_auth,
            json={"agree_to_ai_processing": True},
        ).status_code == 409

        # Enforce candidate-only transcript deletion in PostgreSQL, not just
        # through the FastAPI ownership checks. An authorized employer reviewer
        # is allowed to SELECT transcript evidence but must never DELETE it.
        with engine.begin() as conn:
            conn.execute(text("SET LOCAL ROLE rigor_app"))
            conn.execute(
                text("SELECT set_config('rigor.user_id', :uid, true)"),
                {"uid": reviewer_id},
            )
            conn.execute(
                text("SELECT set_config('rigor.organization_id', :org, true)"),
                {"org": org},
            )
            employer_visible = conn.execute(
                text(
                    """SELECT count(*) FROM employer_ai_interview_messages
                       WHERE candidate_id=:candidate"""
                ),
                {"candidate": candidate_id},
            ).scalar_one()
            assert employer_visible == 2
            forbidden_delete = conn.execute(
                text(
                    """DELETE FROM employer_ai_interview_messages
                       WHERE candidate_id=:candidate RETURNING id"""
                ),
                {"candidate": candidate_id},
            ).all()
            assert forbidden_delete == []
            assert conn.execute(
                text(
                    """SELECT count(*) FROM employer_ai_interview_messages
                       WHERE candidate_id=:candidate"""
                ),
                {"candidate": candidate_id},
            ).scalar_one() == 2

        transcript_unreleased = client.get(
            f"/api/v1/employer/attempts/{attempt_id}/ai-interview",
            headers=reviewer_auth,
        )
        assert transcript_unreleased.status_code == 409

        submitted = client.post(
            f"/api/v1/assessment-attempts/{attempt_id}/submit",
            headers=candidate_auth,
        )
        assert submitted.status_code == 200, submitted.text
        assert submitted.json()["status"] == "submitted"
        employer_transcript = client.get(
            f"/api/v1/employer/attempts/{attempt_id}/ai-interview",
            headers=reviewer_auth,
        )
        assert employer_transcript.status_code == 200, employer_transcript.text
        assert len(employer_transcript.json()["turns"]) == 2
        assert employer_transcript.json()["automated_hiring_decision"] is None
        assert "mcq_answers" not in employer_transcript.text
        assert client.get(
            f"/api/v1/employer/attempts/{attempt_id}/ai-interview",
            headers=candidate_auth,
        ).status_code == 403
        assert client.get(
            f"/api/v1/employer/attempts/{attempt_id}/ai-interview",
            headers=reviewer_second_org,
        ).status_code == 404

        provisional = client.get(
            f"/api/v1/employer/attempts/{attempt_id}/provisional-mcq-score",
            headers=reviewer_auth,
        )
        assert provisional.status_code == 200, provisional.text
        assert provisional.json()["mcq_awarded_marks"] == 0
        assert provisional.json()["mcq_maximum_marks"] == 40
        assert provisional.json()["human_review_pending_marks"] == 60
        assert provisional.json()["hiring_decision"] is None
        assert client.get(
            f"/api/v1/employer/attempts/{attempt_id}/provisional-mcq-score",
            headers=candidate_auth,
        ).status_code == 403
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
        foreign_attempt = client.get(
            f"/api/v1/employer/attempts/{attempt_id}",
            headers=reviewer_second_org,
        )
        assert foreign_attempt.status_code == 404

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

        report = client.get(
            f"/api/v1/employer/assessments/{aid}/report", headers=admin_auth
        )
        assert report.status_code == 200, report.text
        assert report.json()["total_invitations"] == 2
        assert report.json()["accepted_invitations"] == 1
        assert report.json()["revoked_invitations"] == 1
        assert report.json()["total_attempts"] == 1
        assert report.json()["human_reviewed_attempts"] == 1
        scored = report.json()["attempts"][0]
        assert scored["human_reviews"][0]["awarded_marks"] == 52
        assert scored["hiring_decision"] is None
        assert "private_rubric" not in report.text
        assert "acceptance_secret" not in report.text
        csv_report = client.get(
            f"/api/v1/employer/assessments/{aid}/report.csv", headers=admin_auth
        )
        assert csv_report.status_code == 200, csv_report.text
        assert csv_report.headers["content-type"].startswith("text/csv")
        assert csv_report.text.count("\r\n") == 2
        assert ",52,100," in csv_report.text
        assert "answer_key" not in csv_report.text
        assert client.get(
            f"/api/v1/employer/assessments/{aid}/report",
            headers=candidate_auth,
        ).status_code == 403
        assert client.get(
            f"/api/v1/employer/assessments/{aid}/report.csv",
            headers=reviewer_second_org,
        ).status_code == 404

        erased = client.post(
            f"/api/v1/assessment-attempts/{attempt_id}/ai-interview/erase",
            headers=candidate_auth,
        )
        assert erased.status_code == 200, erased.text
        assert erased.json()["status"] == "erased"
        assert erased.json()["messages"] == []
        assert client.post(
            f"/api/v1/assessment-attempts/{attempt_id}/ai-interview/erase",
            headers=other_auth,
        ).status_code == 404
        assert client.get(
            f"/api/v1/employer/attempts/{attempt_id}/ai-interview",
            headers=reviewer_auth,
        ).status_code == 404
        assert client.post(
            f"/api/v1/assessment-attempts/{attempt_id}/ai-interview/consent",
            headers=candidate_auth,
            json={"agree_to_ai_processing": True},
        ).status_code == 409
        with engine.connect() as connection:
            saved_count = connection.execute(
                text(
                    """SELECT count(*) FROM employer_ai_interview_messages
                       WHERE candidate_id=:candidate"""
                ),
                {"candidate": candidate_id},
            ).scalar_one()
        assert saved_count == 0

        # A published SQL coding question keeps its explicit language through
        # employer authoring, candidate acceptance, server persistence and
        # authorized human review, without invoking an unsafe local SQL runner.
        sql_draft = client.post(
            "/api/v1/employer/assessments",
            headers=admin_auth,
            json={
                "slug": f"sql-screen-{uuid4().hex[:10]}",
                "title": "SQL execution-plan comprehension assessment",
                "duration_minutes": 60,
                "questions": [{
                    "number": 1, "kind": "code", "language": "sql",
                    "marks": 100, "options": [],
                    "prompt": "Write a SQL query to count unique event IDs by partition.",
                }],
            },
        )
        assert sql_draft.status_code == 201, sql_draft.text
        sql_assessment_id = sql_draft.json()["id"]
        assert sql_draft.json()["questions"][0]["language"] == "sql"
        published_sql = client.post(
            f"/api/v1/employer/assessments/{sql_assessment_id}/publish",
            headers=reviewer_auth,
            json={
                "rights_evidence": "Independent original SQL assessment authorship verified",
                "technical_evidence": "Reviewer confirmed valid SQL contract and wording",
                "editorial_evidence": "Reviewer confirmed clarity and accessibility",
            },
        )
        assert published_sql.status_code == 200, published_sql.text
        sql_invite = client.post(
            f"/api/v1/employer/assessments/{sql_assessment_id}/invitations",
            headers=admin_auth,
            json={"candidate_id": candidate_id, "expires_in_hours": 1},
        )
        assert sql_invite.status_code == 201, sql_invite.text
        sql_session = client.post(
            "/api/v1/assessment-invitations/accept",
            headers=candidate_auth,
            json={
                "invitation_id": sql_invite.json()["id"],
                "acceptance_secret": sql_invite.json()["acceptance_secret"],
            },
        )
        assert sql_session.status_code == 200, sql_session.text
        assert sql_session.json()["questions"][0]["language"] == "sql"
        sql_attempt_id = sql_session.json()["id"]
        candidate_sql = "SELECT partition_id, COUNT(DISTINCT event_id) FROM events GROUP BY 1"
        saved_sql = client.put(
            f"/api/v1/assessment-attempts/{sql_attempt_id}/responses",
            headers=candidate_auth,
            json={"question_number": 1, "answer_text": candidate_sql},
        )
        assert saved_sql.status_code == 200, saved_sql.text
        assert saved_sql.json()["answers"]["1"] == candidate_sql
        assert client.get(
            f"/api/v1/assessment-attempts/{sql_attempt_id}",
            headers=other_auth,
        ).status_code == 404
        submitted_sql = client.post(
            f"/api/v1/assessment-attempts/{sql_attempt_id}/submit",
            headers=candidate_auth,
        )
        assert submitted_sql.status_code == 200, submitted_sql.text
        reviewed_sql = client.get(
            f"/api/v1/employer/attempts/{sql_attempt_id}", headers=reviewer_auth,
        )
        assert reviewed_sql.status_code == 200, reviewed_sql.text
        assert reviewed_sql.json()["questions"][0]["language"] == "sql"
        assert reviewed_sql.json()["answers"][0]["answer_text"] == candidate_sql
        assert "hidden_tests" not in reviewed_sql.text
        assert "private_rubric" not in reviewed_sql.text



