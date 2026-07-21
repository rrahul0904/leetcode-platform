from __future__ import annotations

import json
from pathlib import Path
from typing import cast

from fastapi.testclient import TestClient
from rigor_api.auth import LocalOIDCProvider
from rigor_api.content_sync import ContentSynchronizer
from rigor_api.main import app
from sqlalchemy import Engine, text

EXTERNAL_ID = "REV-TEST-0001"
SLUG = "review-workflow-fixture"


def cleanup_review_fixture(engine: Engine) -> None:
    with engine.begin() as connection:
        question_id = connection.execute(
            text("SELECT id FROM questions WHERE external_id=:external_id"),
            {"external_id": EXTERNAL_ID},
        ).scalar_one_or_none()
        if question_id is not None:
            version_ids = (
                connection.execute(
                    text("SELECT id FROM question_versions WHERE question_id=:id"),
                    {"id": question_id},
                )
                .scalars()
                .all()
            )
            connection.execute(
                text("UPDATE questions SET current_published_version_id=NULL WHERE id=:id"),
                {"id": question_id},
            )
            if version_ids:
                connection.execute(
                    text(
                        "DELETE FROM review_decisions WHERE review_assignment_id IN "
                        "(SELECT id FROM review_assignments WHERE question_version_id=ANY(:ids))"
                    ),
                    {"ids": version_ids},
                )
                connection.execute(
                    text("DELETE FROM publication_events WHERE question_version_id=ANY(:ids)"),
                    {"ids": version_ids},
                )
                connection.execute(
                    text("DELETE FROM audit_events WHERE resource_id=ANY(:ids)"),
                    {"ids": [str(item) for item in version_ids]},
                )
            connection.execute(
                text("DELETE FROM question_versions WHERE question_id=:id"),
                {"id": question_id},
            )
            connection.execute(text("DELETE FROM questions WHERE id=:id"), {"id": question_id})


def seed_review_fixture(engine: Engine) -> str:
    cleanup_review_fixture(engine)
    with engine.begin() as connection:
        author_id = connection.execute(
            text(
                """
                INSERT INTO users (identity_subject, email, display_name, email_verified)
                VALUES ('local-author', 'author@rigor.test', 'Avery Author', true)
                ON CONFLICT (identity_subject) DO UPDATE SET display_name=EXCLUDED.display_name
                RETURNING id
                """
            )
        ).scalar_one()
        connection.execute(
            text(
                """
                INSERT INTO user_roles (user_id, role_slug)
                VALUES (:user_id, 'content-author') ON CONFLICT DO NOTHING
                """
            ),
            {"user_id": author_id},
        )
        track_id = connection.execute(
            text("SELECT id FROM question_tracks WHERE slug='python-engineering'")
        ).scalar_one()
        question_id = connection.execute(
            text(
                """
                INSERT INTO questions (external_id, slug, primary_track_id)
                VALUES (:external_id, :slug, :track_id) RETURNING id
                """
            ),
            {"external_id": EXTERNAL_ID, "slug": SLUG, "track_id": track_id},
        ).scalar_one()
        version_id = connection.execute(
            text(
                """
                INSERT INTO question_versions (
                    question_id, version, title, problem_statement, expected_seniority,
                    difficulty, conceptual_difficulty, implementation_difficulty,
                    scale, ambiguity, prerequisite_depth, duration_minutes, state,
                    structured_content, content_hash, source_revision
                ) VALUES (
                    :question_id, '1.0.0', 'Review Workflow Fixture', 'Public prompt.',
                    'advanced', 'advanced', 3, 3, 3, 3, 3, 45,
                    'awaiting_technical_review'::content_state,
                    CAST(:structured AS jsonb), :hash, 'review-fixture'
                ) RETURNING id
                """
            ),
            {
                "question_id": question_id,
                "structured": json.dumps(
                    {
                        "learning_objectives": ["Review safely"],
                        "prerequisites": [],
                        "candidate_instructions": ["Explain the design"],
                        "constraints": ["Be deterministic"],
                        "mode_specification": {"tests": []},
                    }
                ),
                "hash": "b" * 64,
            },
        ).scalar_one()
        connection.execute(
            text(
                """
                INSERT INTO provenance_records (
                    question_version_id, author_id, originality_statement,
                    authoring_method, source_notes
                ) VALUES (
                    :version_id, :author_id, 'Original fixture', 'Test fixture', '[]'::jsonb
                )
                """
            ),
            {"version_id": version_id, "author_id": author_id},
        )
        connection.execute(
            text(
                """
                INSERT INTO validation_runs (
                    question_version_id, validator_version, status, findings,
                    started_at, completed_at
                ) VALUES (
                    :version_id, 'test', 'passed', '[]'::jsonb,
                    CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                )
                """
            ),
            {"version_id": version_id},
        )
    return str(version_id)


def test_independent_review_publication_deprecation_and_audit() -> None:
    with TestClient(app) as client:
        engine = cast(Engine, app.state.database_engine)
        provider = cast(LocalOIDCProvider, app.state.local_oidc_provider)
        version_id = seed_review_fixture(engine)

        tokens = {
            identity: provider.issue_test_access_token(identity, expires_in=900)
            for identity in (
                "technical-reviewer",
                "editorial-reviewer",
                "platform-administrator",
                "author",
            )
        }
        headers = {
            identity: {"Authorization": f"Bearer {token}"} for identity, token in tokens.items()
        }
        for identity in (
            "technical-reviewer",
            "editorial-reviewer",
            "platform-administrator",
        ):
            assert client.get("/api/v1/reviews", headers=headers[identity]).status_code == 200

        author_attempt = client.post(
            f"/api/v1/reviews/{version_id}/technical-decision",
            headers=headers["author"],
            json={"outcome": "approved", "reason": "I approve my own authored work."},
        )
        assert author_attempt.status_code == 403

        admin_headers = headers["platform-administrator"]
        technical_assignment = client.put(
            f"/api/v1/reviews/{version_id}/assignment",
            headers=admin_headers,
            json={"kind": "technical", "reviewer_subject_id": "local-technical-reviewer"},
        )
        assert technical_assignment.status_code == 200
        editorial_assignment = client.put(
            f"/api/v1/reviews/{version_id}/assignment",
            headers=admin_headers,
            json={"kind": "editorial", "reviewer_subject_id": "local-editorial-reviewer"},
        )
        assert editorial_assignment.status_code == 200

        technical = client.post(
            f"/api/v1/reviews/{version_id}/technical-decision",
            headers=headers["technical-reviewer"],
            json={
                "outcome": "approved",
                "reason": "Reference behavior and edge cases meet the technical standard.",
            },
        )
        assert technical.status_code == 200
        assert technical.json()["state"] == "awaiting_editorial_review"

        wrong_reviewer = client.post(
            f"/api/v1/reviews/{version_id}/editorial-decision",
            headers=headers["technical-reviewer"],
            json={
                "outcome": "approved",
                "reason": "The same reviewer must not provide editorial approval.",
            },
        )
        assert wrong_reviewer.status_code == 403

        editorial = client.post(
            f"/api/v1/reviews/{version_id}/editorial-decision",
            headers=headers["editorial-reviewer"],
            json={
                "outcome": "approved",
                "reason": "The prompt is clear, original, accessible, and publication ready.",
            },
        )
        assert editorial.status_code == 200
        assert editorial.json()["state"] == "approved"

        publish_headers = {**admin_headers, "Idempotency-Key": "review-fixture-publication-1"}
        published = client.post(f"/api/v1/reviews/{version_id}/publish", headers=publish_headers)
        assert published.status_code == 200
        assert published.json()["state"] == "published"
        repeated = client.post(f"/api/v1/reviews/{version_id}/publish", headers=publish_headers)
        assert repeated.status_code == 200

        candidate = provider.issue_test_access_token("candidate", expires_in=900)
        candidate_headers = {"Authorization": f"Bearer {candidate}"}
        visible = client.get(f"/api/v1/questions/{SLUG}", headers=candidate_headers)
        assert visible.status_code == 200

        deprecated = client.post(
            f"/api/v1/reviews/{version_id}/transition/deprecated", headers=admin_headers
        )
        assert deprecated.status_code == 200
        assert client.get(f"/api/v1/questions/{SLUG}", headers=candidate_headers).status_code == 404

        rollback = ContentSynchronizer(engine, Path("content"), "review-test-rollback").rollback(
            EXTERNAL_ID, "1.0.0"
        )
        assert rollback.rolled_back == 1
        assert client.get(f"/api/v1/questions/{SLUG}", headers=candidate_headers).status_code == 200

        with engine.connect() as connection:
            assert (
                connection.execute(
                    text(
                        """
                    SELECT count(*) FROM audit_events
                    WHERE resource_id=:version_id AND action IN (
                            'review.assigned', 'review.decided', 'content.published',
                            'content.deprecated', 'content.rollback'
                    )
                    """
                    ),
                    {"version_id": version_id},
                ).scalar_one()
                == 7
            )
            assert (
                connection.execute(
                    text(
                        "SELECT count(*) FROM review_decisions d JOIN review_assignments a "
                        "ON a.id=d.review_assignment_id WHERE a.question_version_id=:version_id"
                    ),
                    {"version_id": version_id},
                ).scalar_one()
                == 2
            )
        cleanup_review_fixture(engine)
