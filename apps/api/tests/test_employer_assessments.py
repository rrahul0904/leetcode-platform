"""Two-sided assessment HTTP flow against actual PostgreSQL forced-RLS tables."""

from __future__ import annotations

import json
from uuid import uuid4

import jwt
from fastapi.testclient import TestClient
from rigor_api.auth import LOCAL_IDENTITIES, LocalIdentity, LocalOIDCProvider
from rigor_api.employer_code_execution_worker import EmployerCodeWorker
from rigor_api.execution_kubernetes import SandboxHandle, SandboxObservation
from rigor_api.execution_results import RESULT_PREFIX
from rigor_api.execution_sqs import SqsReceivedMessage
from rigor_api.main import app
from rigor_api.schemas import Role
from sqlalchemy import Engine, text


class _EmployerQueueRecorder:
    def __init__(self) -> None:
        self.sent: list[str] = []
        self.deleted: list[str] = []

    def send_message(self, body: str) -> str:
        self.sent.append(body)
        return f"message-{len(self.sent)}"

    def delete_message(self, handle: str) -> None:
        self.deleted.append(handle)

    def change_message_visibility(self, handle: str, timeout_seconds: int) -> None:
        pass


class _SqlRunnerSimulator:
    """Mock only the isolated EKS interface, never execute submitted SQL in API."""

    def __init__(self) -> None:
        self.requests: dict[str, dict[str, object]] = {}
        self.cleaned: list[str] = []

    def create_sql_execution(
        self, *, execution_id: object, request_payload: dict[str, object],
        profile_name: str,
    ) -> SandboxHandle:
        assert profile_name == "sql-small"
        self.requests[str(execution_id)] = request_payload
        assert all("expected" not in test for test in request_payload["tests"])
        return SandboxHandle(
            execution_id=execution_id,
            namespace="rigor-execution", job_name="isolated-simulated",
            input_secret_name="isolated-simulated-input",
        )

    def observe(self, handle: SandboxHandle) -> SandboxObservation:
        req = self.requests[str(handle.execution_id)]
        rows = {"sample_one": [[1, 1]], "hidden_one": [[1, 2]]}
        tests = [
            {
                "id": test["id"], "visibility": test["visibility"], "ok": True,
                "actual": {"columns": ["partition_id", "count"], "rows": rows[test["id"]]},
                "error_category": None,
            }
            for test in req["tests"]
        ]
        response = {
            "schema_version": 1, "execution_id": str(handle.execution_id),
            "attempt": req["attempt"], "status": "COMPLETED", "runtime_ms": 18,
            "exit_code": 0, "stdout": "", "stderr": "",
            "error_category": None, "tests": tests,
        }
        return SandboxObservation(
            state="SUCCEEDED",
            logs=RESULT_PREFIX + json.dumps(response, separators=(",", ":")),
        )

    def cleanup(self, handle: SandboxHandle) -> None:
        self.cleaned.append(str(handle.execution_id))


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

        # The reviewer may see attempt status before submission, but not read
        # the candidate's draft responses or silently pre-grade a live test.
        premature_review = client.get(
            f"/api/v1/employer/attempts/{attempt_id}", headers=reviewer_auth,
        )
        assert premature_review.status_code == 409
        assert "Diagnose, quarantine" not in premature_review.text
        assert client.get(
            f"/api/v1/employer/attempts/{attempt_id}",
            headers=reviewer_second_org,
        ).status_code == 404

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
        # Simulate a crash after persisting the candidate turn but before the
        # AI provider returned. The candidate cannot steal a live reservation;
        # after the timeout the orphan is removed and completed turns survive.
        interrupted_id = "interrupted-" + uuid4().hex
        with engine.begin() as conn:
            conn.execute(
                text(
                    """INSERT INTO employer_ai_interview_messages
                       (session_id, organization_id, candidate_id,
                        sequence_number, role, content, request_id)
                       VALUES (:session, :org, :candidate, 2, 'candidate',
                               'Orphaned request must not remain', :request)"""
                ),
                {
                    "session": consent.json()["id"], "org": org,
                    "candidate": candidate_id, "request": interrupted_id,
                },
            )
            conn.execute(
                text(
                    """UPDATE employer_ai_interview_sessions
                       SET pending_request_id=:request,
                           pending_at=CURRENT_TIMESTAMP
                       WHERE id=:session"""
                ),
                {"request": interrupted_id, "session": consent.json()["id"]},
            )
        pending_recovery = client.post(
            f"/api/v1/assessment-attempts/{attempt_id}/ai-interview/recover",
            headers=candidate_auth,
        )
        assert pending_recovery.status_code == 409
        assert client.post(
            f"/api/v1/assessment-attempts/{attempt_id}/ai-interview/recover",
            headers=other_auth,
        ).status_code == 404
        with engine.begin() as conn:
            conn.execute(
                text(
                    """UPDATE employer_ai_interview_sessions
                       SET pending_at=CURRENT_TIMESTAMP - INTERVAL '100 seconds'
                       WHERE id=:session"""
                ),
                {"session": consent.json()["id"]},
            )
        recovered = client.post(
            f"/api/v1/assessment-attempts/{attempt_id}/ai-interview/recover",
            headers=candidate_auth,
        )
        assert recovered.status_code == 200, recovered.text
        assert recovered.json()["turn_count"] == 1
        assert len(recovered.json()["messages"]) == 2
        assert all(
            turn["request_id"] != interrupted_id
            for turn in recovered.json()["messages"]
        )
        assert client.post(
            f"/api/v1/assessment-attempts/{attempt_id}/ai-interview/recover",
            headers=candidate_auth,
        ).status_code == 200

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
        unready = client.get(
            f"/api/v1/employer/assessments/{sql_assessment_id}/code-test-bundles",
            headers=reviewer_auth,
        )
        assert unready.status_code == 200, unready.text
        assert unready.json()[0]["ready"] is False
        assert unready.json()[0]["bundle_sha256"] is None
        assert client.get(
            f"/api/v1/employer/assessments/{sql_assessment_id}/code-test-bundles",
            headers=candidate_auth,
        ).status_code == 403
        # Wave 2: original confidential SQL fixture metadata is validated,
        # stored under private RLS, and absent from candidate-visible blueprints.
        base_key = client.put(
            f"/api/v1/employer/assessments/{sql_assessment_id}/private-key",
            headers=admin_auth,
            json={"mcq_answers": {},
                  "reviewer_guidance": "Independent SQL evaluation requires human review"},
        )
        assert base_key.status_code == 200, base_key.text
        without_fixtures = client.post(
            f"/api/v1/employer/assessments/{sql_assessment_id}/publish",
            headers=reviewer_auth,
            json={
                "rights_evidence": "Independent original SQL assessment authorship verified",
                "technical_evidence": "Reviewer verified question and intended grading",
                "editorial_evidence": "Reviewer verified question wording and access",
            },
        )
        assert without_fixtures.status_code == 409
        assert "private test cases" in without_fixtures.text
        private_cases = {
            "language": "sql",
            "cases": [
                {
                    "case_id": "sample_one", "visibility": "sample",
                    "input_data": json.dumps({
                        "schema_sql": "CREATE TABLE events (event_id INT, partition_id INT)",
                        "seed_sql": "INSERT INTO events VALUES (1,1)",
                    }),
                    "expected_output": json.dumps({
                        "columns": ["partition_id", "count"], "rows": [[1, 1]],
                    }),
                    "points": 0,
                },
                {
                    "case_id": "hidden_one", "visibility": "hidden",
                    "input_data": json.dumps({
                        "schema_sql": "CREATE TABLE events (event_id INT, partition_id INT)",
                        "seed_sql": "INSERT INTO events VALUES (1,1),(1,1),(2,1)",
                    }),
                    "expected_output": json.dumps({
                        "columns": ["partition_id", "count"], "rows": [[1, 2]],
                    }),
                    "points": 100,
                },
            ],
        }
        wrong_runtime = client.put(
            f"/api/v1/employer/assessments/{sql_assessment_id}/code-test-bundles/1",
            headers=admin_auth,
            json={**private_cases, "language": "python"},
        )
        assert wrong_runtime.status_code == 422
        staged = client.put(
            f"/api/v1/employer/assessments/{sql_assessment_id}/code-test-bundles/1",
            headers=admin_auth, json=private_cases,
        )
        assert staged.status_code == 200, staged.text
        assert staged.json()["hidden_count"] == 1
        assert "hidden_one" not in staged.text
        reviewer_status = client.get(
            f"/api/v1/employer/assessments/{sql_assessment_id}/code-test-bundles",
            headers=reviewer_auth,
        )
        assert reviewer_status.status_code == 200, reviewer_status.text
        assert reviewer_status.json()[0]["ready"] is True
        assert reviewer_status.json()[0]["hidden_count"] == 1
        assert reviewer_status.json()[0]["bundle_sha256"] == staged.json()["bundle_sha256"]
        assert "hidden_one" not in reviewer_status.text
        assert "INSERT INTO events" not in reviewer_status.text
        assert client.put(
            f"/api/v1/employer/assessments/{sql_assessment_id}/code-test-bundles/1",
            headers=candidate_auth, json=private_cases,
        ).status_code == 403
        # Updating the regular MCQ rubric must preserve privately staged cases.
        assert client.put(
            f"/api/v1/employer/assessments/{sql_assessment_id}/private-key",
            headers=admin_auth,
            json={"mcq_answers": {},
                  "reviewer_guidance": "Reviewed confidential SQL grading test data"},
        ).status_code == 200
        with engine.connect() as connection:
            stored_private = connection.execute(
                text("""SELECT private_rubric FROM employer_assessment_private_keys
                          WHERE assessment_version_id=:assessment"""),
                {"assessment": sql_assessment_id},
            ).scalar_one()
        assert stored_private["code_test_bundles"]["1"]["bundle"]["cases"][1][
            "case_id"
        ] == "hidden_one"
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
        assert client.put(
            f"/api/v1/employer/assessments/{sql_assessment_id}/code-test-bundles/1",
            headers=admin_auth, json=private_cases,
        ).status_code == 409
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
        assert "hidden_one" not in sql_session.text
        sql_attempt_id = sql_session.json()["id"]
        candidate_sql = "SELECT partition_id, COUNT(DISTINCT event_id) FROM events GROUP BY 1"
        saved_sql = client.put(
            f"/api/v1/assessment-attempts/{sql_attempt_id}/responses",
            headers=candidate_auth,
            json={"question_number": 1, "answer_text": candidate_sql},
        )
        assert saved_sql.status_code == 200, saved_sql.text
        assert saved_sql.json()["answers"]["1"] == candidate_sql
        run_headers = {**candidate_auth, "Idempotency-Key": "sql-run-first-check"}
        first_run = client.post(
            f"/api/v1/assessment-attempts/{sql_attempt_id}/code-executions",
            headers=run_headers,
            json={"question_number": 1, "mode": "RUN"},
        )
        assert first_run.status_code == 202, first_run.text
        assert first_run.json()["status"] == "queued"
        assert first_run.json()["awarded_marks"] is None
        assert first_run.json()["public_results"] is None
        assert first_run.json()["hidden_total"] is None
        repeat_run = client.post(
            f"/api/v1/assessment-attempts/{sql_attempt_id}/code-executions",
            headers=run_headers,
            json={"question_number": 1, "mode": "RUN"},
        )
        assert repeat_run.status_code == 202
        assert repeat_run.json()["id"] == first_run.json()["id"]
        assert repeat_run.json()["duplicate"] is True
        second_run = client.post(
            f"/api/v1/assessment-attempts/{sql_attempt_id}/code-executions",
            headers={**candidate_auth, "Idempotency-Key": "sql-run-second-check"},
            json={"question_number": 1, "mode": "RUN"},
        )
        assert second_run.status_code == 202, second_run.text
        assert client.post(
            f"/api/v1/assessment-attempts/{sql_attempt_id}/code-executions",
            headers={**candidate_auth, "Idempotency-Key": "sql-run-exhausted"},
            json={"question_number": 1, "mode": "RUN"},
        ).status_code == 429
        assert client.get(
            f"/api/v1/assessment-attempts/{sql_attempt_id}/code-executions/{first_run.json()['id']}",
            headers=other_auth,
        ).status_code == 404
        assert client.get(
            f"/api/v1/assessment-attempts/{sql_attempt_id}/code-executions/{first_run.json()['id']}",
            headers=candidate_auth,
        ).status_code == 200
        assert client.post(
            f"/api/v1/assessment-attempts/{sql_attempt_id}/code-executions",
            headers={**candidate_auth, "Idempotency-Key": "sql-submit-too-early"},
            json={"question_number": 1, "mode": "SUBMIT"},
        ).status_code == 409
        assert client.get(
            f"/api/v1/assessment-attempts/{sql_attempt_id}",
            headers=other_auth,
        ).status_code == 404
        submitted_sql = client.post(
            f"/api/v1/assessment-attempts/{sql_attempt_id}/submit",
            headers=candidate_auth,
        )
        assert submitted_sql.status_code == 200, submitted_sql.text
        # The backend MUST queue the final hidden grade in its own submit
        # transaction; browser follow-up requests are no longer required.
        queued_receipts = client.get(
            f"/api/v1/assessment-attempts/{sql_attempt_id}/code-executions",
            headers=candidate_auth,
        )
        assert queued_receipts.status_code == 200, queued_receipts.text
        assert len(queued_receipts.json()) == 3
        final_receipt = next(
            item for item in queued_receipts.json()
            if item["execution_mode"] == "SUBMIT"
        )
        assert final_receipt["status"] == "queued"
        assert final_receipt["awarded_marks"] is None
        assert "hidden_one" not in queued_receipts.text
        assert client.get(
            f"/api/v1/assessment-attempts/{sql_attempt_id}/code-executions",
            headers=other_auth,
        ).status_code == 404
        # Retry with the deterministic idempotency key sees the SAME job.
        final_code = client.post(
            f"/api/v1/assessment-attempts/{sql_attempt_id}/code-executions",
            headers={**candidate_auth,
                     "Idempotency-Key": f"final-{sql_attempt_id}-1"},
            json={"question_number": 1, "mode": "SUBMIT"},
        )
        assert final_code.status_code == 202, final_code.text
        assert final_code.json()["id"] == final_receipt["id"]
        assert final_code.json()["duplicate"] is True
        assert client.post(
            f"/api/v1/assessment-attempts/{sql_attempt_id}/submit",
            headers=candidate_auth,
        ).status_code == 200
        assert client.post(
            f"/api/v1/assessment-attempts/{sql_attempt_id}/code-executions",
            headers={**candidate_auth, "Idempotency-Key": "sql-hidden-repeat-grade"},
            json={"question_number": 1, "mode": "SUBMIT"},
        ).status_code == 409
        assert client.post(
            f"/api/v1/assessment-attempts/{sql_attempt_id}/code-executions",
            headers={**candidate_auth, "Idempotency-Key": "sql-run-after-final"},
            json={"question_number": 1, "mode": "RUN"},
        ).status_code == 409
        with engine.connect() as connection:
            queued_count = connection.execute(
                text("""SELECT count(*) FROM employer_code_execution_outbox o
                        JOIN employer_code_executions e ON e.id=o.execution_id
                        WHERE e.attempt_id=:attempt"""),
                {"attempt": sql_attempt_id},
            ).scalar_one()
        assert queued_count == 3
        sql_human_review = {
            "scores": [
                {"question_number": 1, "awarded_marks": 100,
                 "evidence_note": "Source code matches expected grouped aggregation"}
            ],
            "overall_notes": "Reviewer confirms the final grading receipt and code quality",
        }
        pending_review = client.post(
            f"/api/v1/employer/attempts/{sql_attempt_id}/reviews",
            headers=reviewer_auth, json=sql_human_review,
        )
        assert pending_review.status_code == 409, pending_review.text
        assert "must finish" in pending_review.text

        # Fully exercise the durable outbox, trusted job claim, sandbox
        # protocol, confidential comparator and stored scoring receipt.
        # _SqlRunnerSimulator supplies runner results; this is NOT live EKS.
        queue_recorder = _EmployerQueueRecorder()
        simulated_runner = _SqlRunnerSimulator()
        worker = EmployerCodeWorker(
            engine=engine, queue=queue_recorder, sandbox=simulated_runner,
            worker_id="integration-worker",
        )
        assert worker.publish_outbox_once() >= 3
        queued_sql_messages = [
            event for event in queue_recorder.sent
            if json.loads(event)["execution_id"] in {
                item["id"] for item in queued_receipts.json()
            }
        ]
        assert len(queued_sql_messages) == 3
        for index, event in enumerate(queued_sql_messages):
            assert "SELECT partition_id" not in event
            assert "hidden_one" not in event
            assert worker.process_message(SqsReceivedMessage(
                message_id=f"sql-{index}", receipt_handle=f"receipt-{index}",
                body=event,
            ))
        assert len(simulated_runner.cleaned) == 3
        after_worker = client.get(
            f"/api/v1/assessment-attempts/{sql_attempt_id}/code-executions",
            headers=candidate_auth,
        )
        assert after_worker.status_code == 200, after_worker.text
        assert all(item["status"] == "completed" for item in after_worker.json())
        graded_final = next(
            item for item in after_worker.json() if item["execution_mode"] == "SUBMIT"
        )
        assert graded_final["awarded_marks"] == 100
        assert graded_final["hidden_total"] == 1
        assert graded_final["hidden_passed"] == 1
        assert "hidden_one" not in after_worker.text
        assert "[[1, 2]]" not in after_worker.text
        assert all(
            item["hidden_total"] == 0 and item["awarded_marks"] is None
            for item in after_worker.json() if item["execution_mode"] == "RUN"
        )
        reviewer_code = client.get(
            f"/api/v1/employer/attempts/{sql_attempt_id}/code-executions",
            headers=reviewer_auth,
        )
        assert reviewer_code.status_code == 200, reviewer_code.text
        assert len(reviewer_code.json()) == 3
        assert "hidden_one" not in reviewer_code.text
        completed_review = client.post(
            f"/api/v1/employer/attempts/{sql_attempt_id}/reviews",
            headers=reviewer_auth, json=sql_human_review,
        )
        assert completed_review.status_code == 201, completed_review.text
        assert completed_review.json()["awarded_marks"] == 100
        # A principal with no membership is denied before tenant lookup.
        assert client.get(
            f"/api/v1/employer/attempts/{sql_attempt_id}/code-executions",
            headers=wrong_org_auth,
        ).status_code == 403
        reviewed_sql = client.get(
            f"/api/v1/employer/attempts/{sql_attempt_id}", headers=reviewer_auth,
        )
        assert reviewed_sql.status_code == 200, reviewed_sql.text
        assert reviewed_sql.json()["questions"][0]["language"] == "sql"
        assert reviewed_sql.json()["answers"][0]["answer_text"] == candidate_sql
        assert "hidden_tests" not in reviewed_sql.text
        assert "private_rubric" not in reviewed_sql.text



