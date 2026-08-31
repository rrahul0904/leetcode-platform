from __future__ import annotations

from typing import cast

from fastapi.testclient import TestClient
from rigor_api.auth import LOCAL_IDENTITIES, LocalIdentity, LocalOIDCProvider
from rigor_api.main import app
from rigor_api.schemas import Role
from sqlalchemy import Engine
from test_published_catalog import cleanup_catalog_fixtures, seed_catalog_fixtures
from test_question_engagement import cleanup_candidate

SECOND_IDENTITY_KEY = "practice-candidate-b"
SECOND_SUBJECT = "local-practice-candidate-b"


def test_practice_sessions_are_private_to_the_authenticated_candidate() -> None:
    with TestClient(app) as client:
        engine = cast(Engine, app.state.database_engine)
        provider = cast(LocalOIDCProvider, app.state.local_oidc_provider)
        seed_catalog_fixtures(engine)
        cleanup_candidate(engine, "local-candidate")
        cleanup_candidate(engine, SECOND_SUBJECT)
        LOCAL_IDENTITIES[SECOND_IDENTITY_KEY] = LocalIdentity(
            SECOND_SUBJECT,
            "practice-b@rigor.test",
            "Practice Candidate B",
            (Role.candidate,),
        )
        try:
            token_a = provider.issue_test_access_token("candidate", expires_in=900)
            token_b = provider.issue_test_access_token(SECOND_IDENTITY_KEY, expires_in=900)
            headers_a = {"Authorization": f"Bearer {token_a}"}
            headers_b = {"Authorization": f"Bearer {token_b}"}

            created = client.post(
                "/api/v1/practice-sessions",
                headers=headers_a,
                json={
                    "question_slug": "candidate-safe-cache",
                    "runtime": "python3.13",
                },
            )
            assert created.status_code == 201
            session_id = created.json()["id"]

            owner_read = client.get(
                f"/api/v1/practice-sessions/{session_id}",
                headers=headers_a,
            )
            assert owner_read.status_code == 200

            other_read = client.get(
                f"/api/v1/practice-sessions/{session_id}",
                headers=headers_b,
            )
            assert other_read.status_code == 404

            other_patch = client.patch(
                f"/api/v1/practice-sessions/{session_id}",
                headers=headers_b,
                json={"draft_code": "candidate B must not overwrite A"},
            )
            assert other_patch.status_code == 404

            other_list = client.get("/api/v1/practice-sessions", headers=headers_b)
            assert other_list.status_code == 200
            assert all(item["id"] != session_id for item in other_list.json())

            owner_after = client.get(
                f"/api/v1/practice-sessions/{session_id}",
                headers=headers_a,
            )
            assert owner_after.status_code == 200
            assert owner_after.json()["draft_code"] != "candidate B must not overwrite A"
        finally:
            LOCAL_IDENTITIES.pop(SECOND_IDENTITY_KEY, None)
            cleanup_candidate(engine, "local-candidate")
            cleanup_candidate(engine, SECOND_SUBJECT)
            cleanup_catalog_fixtures(engine)
