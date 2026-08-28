from __future__ import annotations

from typing import cast

from fastapi.testclient import TestClient
from rigor_api.auth import LOCAL_IDENTITIES, LocalIdentity, LocalOIDCProvider
from rigor_api.main import app
from rigor_api.schemas import Role
from sqlalchemy import Engine, text

from test_published_catalog import cleanup_catalog_fixtures, seed_catalog_fixtures

SECOND_IDENTITY_KEY = "candidate-b"
SECOND_SUBJECT = "local-candidate-b"


def cleanup_candidate(engine: Engine, subject: str) -> None:
    with engine.begin() as connection:
        user_id = connection.execute(
            text("SELECT id FROM users WHERE identity_subject=:subject"),
            {"subject": subject},
        ).scalar_one_or_none()
        if user_id is not None:
            connection.execute(
                text("DELETE FROM audit_events WHERE actor_user_id=:user_id"),
                {"user_id": user_id},
            )
            connection.execute(
                text("DELETE FROM users WHERE id=:user_id"),
                {"user_id": user_id},
            )


def test_candidate_bookmarks_and_notes_are_isolated_by_rls() -> None:
    with TestClient(app) as client:
        engine = cast(Engine, app.state.database_engine)
        provider = cast(LocalOIDCProvider, app.state.local_oidc_provider)
        seed_catalog_fixtures(engine)
        cleanup_candidate(engine, "local-candidate")
        cleanup_candidate(engine, SECOND_SUBJECT)
        LOCAL_IDENTITIES[SECOND_IDENTITY_KEY] = LocalIdentity(
            SECOND_SUBJECT,
            "candidate-b@rigor.test",
            "Bailey Candidate",
            (Role.candidate,),
        )
        try:
            token_a = provider.issue_test_access_token("candidate", expires_in=900)
            token_b = provider.issue_test_access_token(SECOND_IDENTITY_KEY, expires_in=900)
            headers_a = {"Authorization": f"Bearer {token_a}"}
            headers_b = {"Authorization": f"Bearer {token_b}"}

            bookmarked = client.put(
                "/api/v1/questions/candidate-safe-cache/bookmark",
                headers=headers_a,
            )
            assert bookmarked.status_code == 200
            assert bookmarked.json()["bookmarked"] is True

            note = client.post(
                "/api/v1/questions/candidate-safe-cache/notes",
                headers=headers_a,
                json={"body": "Candidate A private note"},
            )
            assert note.status_code == 201
            note_id = note.json()["id"]

            engagement_b = client.get(
                "/api/v1/questions/candidate-safe-cache/engagement",
                headers=headers_b,
            )
            assert engagement_b.status_code == 200
            assert engagement_b.json()["bookmarked"] is False
            assert engagement_b.json()["notes"] == []

            bookmarks_b = client.get(
                "/api/v1/candidate/bookmarks",
                headers=headers_b,
            )
            assert bookmarks_b.status_code == 200
            assert bookmarks_b.json() == []

            bookmarked_catalog_b = client.get(
                "/api/v1/candidate/bookmarked-questions",
                headers=headers_b,
            )
            assert bookmarked_catalog_b.status_code == 200
            assert bookmarked_catalog_b.json()["total"] == 0

            forbidden_update = client.patch(
                f"/api/v1/questions/candidate-safe-cache/notes/{note_id}",
                headers=headers_b,
                json={"body": "Candidate B must not overwrite this"},
            )
            assert forbidden_update.status_code == 404

            forbidden_delete = client.delete(
                f"/api/v1/questions/candidate-safe-cache/notes/{note_id}",
                headers=headers_b,
            )
            assert forbidden_delete.status_code == 404

            engagement_a = client.get(
                "/api/v1/questions/candidate-safe-cache/engagement",
                headers=headers_a,
            )
            assert engagement_a.status_code == 200
            assert engagement_a.json()["bookmarked"] is True
            assert [item["body"] for item in engagement_a.json()["notes"]] == [
                "Candidate A private note"
            ]
        finally:
            LOCAL_IDENTITIES.pop(SECOND_IDENTITY_KEY, None)
            cleanup_catalog_fixtures(engine)
            cleanup_candidate(engine, "local-candidate")
            cleanup_candidate(engine, SECOND_SUBJECT)
