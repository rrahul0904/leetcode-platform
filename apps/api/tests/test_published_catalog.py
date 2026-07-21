from __future__ import annotations

import json
from typing import cast

from fastapi.testclient import TestClient
from rigor_api.auth import LocalOIDCProvider
from rigor_api.main import app
from sqlalchemy import Engine, text

PUBLISHED_EXTERNAL_ID = "CAT-TEST-0001"
UNPUBLISHED_EXTERNAL_ID = "CAT-TEST-0002"
HIDDEN_SENTINEL = "NEVER_EXPOSE_HIDDEN_INPUT"
SOLUTION_SENTINEL = "NEVER_EXPOSE_REFERENCE_SOLUTION"
INTERVIEWER_SENTINEL = "NEVER_EXPOSE_INTERVIEWER_GUIDANCE"


def cleanup_catalog_fixtures(engine: Engine) -> None:
    with engine.begin() as connection:
        question_ids = (
            connection.execute(
                text("SELECT id FROM questions WHERE external_id IN (:published, :unpublished)"),
                {"published": PUBLISHED_EXTERNAL_ID, "unpublished": UNPUBLISHED_EXTERNAL_ID},
            )
            .scalars()
            .all()
        )
        if question_ids:
            connection.execute(
                text(
                    "UPDATE questions SET current_published_version_id = NULL "
                    "WHERE id = ANY(:question_ids)"
                ),
                {"question_ids": question_ids},
            )
            connection.execute(
                text("DELETE FROM question_versions WHERE question_id = ANY(:question_ids)"),
                {"question_ids": question_ids},
            )
            connection.execute(
                text("DELETE FROM questions WHERE id = ANY(:question_ids)"),
                {"question_ids": question_ids},
            )


def seed_catalog_fixtures(engine: Engine) -> None:
    cleanup_catalog_fixtures(engine)
    structured_content = {
        "learning_objectives": ["Apply deterministic cache semantics"],
        "prerequisites": ["Python mappings"],
        "candidate_instructions": ["Implement the requested behavior"],
        "constraints": ["Do not use wall-clock time"],
        "interviewer_instructions": [INTERVIEWER_SENTINEL],
        "strong_answer_indicators": [INTERVIEWER_SENTINEL],
        "mode_specification": {
            "tests": [
                {
                    "id": "CAT-P01",
                    "name": "public example",
                    "visibility": "public",
                    "input": {"values": [1, 2]},
                    "expected_output": 3,
                },
                {
                    "id": "CAT-H01",
                    "name": "hidden boundary",
                    "visibility": "hidden",
                    "input": HIDDEN_SENTINEL,
                    "expected_output": 0,
                },
            ]
        },
    }
    with engine.begin() as connection:
        track_id = connection.execute(
            text("SELECT id FROM question_tracks WHERE slug = 'python-engineering'")
        ).scalar_one()
        skill_id = connection.execute(
            text(
                """
                INSERT INTO skills (slug, name, category)
                VALUES ('catalog-test-skill', 'Catalog Test Skill', 'python-engineering')
                ON CONFLICT (slug) DO UPDATE SET name=EXCLUDED.name
                RETURNING id
                """
            )
        ).scalar_one()
        tag_id = connection.execute(
            text(
                """
                INSERT INTO company_style_tags (slug, name, independence_disclaimer)
                VALUES ('catalog-test-style', 'Catalog Test Style', 'Independent curriculum.')
                ON CONFLICT (slug) DO UPDATE SET name=EXCLUDED.name
                RETURNING id
                """
            )
        ).scalar_one()
        for external_id, slug, state in (
            (PUBLISHED_EXTERNAL_ID, "candidate-safe-cache", "published"),
            (UNPUBLISHED_EXTERNAL_ID, "unpublished-candidate-safe-cache", "approved"),
        ):
            question_id = connection.execute(
                text(
                    """
                    INSERT INTO questions (external_id, slug, primary_track_id)
                    VALUES (:external_id, :slug, :track_id) RETURNING id
                    """
                ),
                {"external_id": external_id, "slug": slug, "track_id": track_id},
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
                        :question_id, '1.0.0', 'Candidate Safe Cache',
                        'Build a deterministic bounded cache.', 'advanced', 'advanced',
                        3, 4, 3, 3, 3, 60, CAST(:state AS content_state),
                        CAST(:structured AS jsonb), :content_hash, 'catalog-test'
                    ) RETURNING id
                    """
                ),
                {
                    "question_id": question_id,
                    "state": state,
                    "structured": json.dumps(structured_content),
                    "content_hash": "a" * 64,
                },
            ).scalar_one()
            connection.execute(
                text(
                    "INSERT INTO question_skills (question_version_id, skill_id, is_primary) "
                    "VALUES (:version_id, :skill_id, true)"
                ),
                {"version_id": version_id, "skill_id": skill_id},
            )
            connection.execute(
                text(
                    """
                    INSERT INTO question_company_tags (
                        question_version_id, company_style_tag_id,
                        relevance_rationale, public_theme_sources
                    ) VALUES (:version_id, :tag_id, 'Tests catalog filtering.', '[]'::jsonb)
                    """
                ),
                {"version_id": version_id, "tag_id": tag_id},
            )
            connection.execute(
                text(
                    """
                    INSERT INTO solutions (
                        question_version_id, reference_solution, explanation,
                        trade_off_analysis, source_content_hash
                    ) VALUES (:version_id, :solution, 'private', '{}'::jsonb, :content_hash)
                    """
                ),
                {
                    "version_id": version_id,
                    "solution": SOLUTION_SENTINEL,
                    "content_hash": "a" * 64,
                },
            )
            if state == "published":
                connection.execute(
                    text(
                        "UPDATE questions SET current_published_version_id=:version_id "
                        "WHERE id=:question_id"
                    ),
                    {"version_id": version_id, "question_id": question_id},
                )


def test_candidate_catalog_is_published_filtered_and_leakage_safe() -> None:
    with TestClient(app) as client:
        engine = cast(Engine, app.state.database_engine)
        provider = cast(LocalOIDCProvider, app.state.local_oidc_provider)
        seed_catalog_fixtures(engine)
        token = provider.issue_test_access_token("candidate", expires_in=900)
        headers = {"Authorization": f"Bearer {token}"}

        anonymous = client.get("/api/v1/questions")
        assert anonymous.status_code == 401

        catalog = client.get(
            "/api/v1/questions",
            headers=headers,
            params={
                "query": "cache",
                "track": "python-engineering",
                "skill": "catalog-test-skill",
                "difficulty": "advanced",
                "role": "advanced",
                "company_style": "catalog-test-style",
                "completion_status": "not_started",
                "sort": "duration",
            },
        )
        assert catalog.status_code == 200
        assert catalog.json()["total"] == 1
        assert catalog.json()["items"][0]["slug"] == "candidate-safe-cache"

        detail = client.get("/api/v1/questions/candidate-safe-cache", headers=headers)
        assert detail.status_code == 200
        assert detail.json()["public_examples"] == [
            {
                "id": "CAT-P01",
                "name": "public example",
                "input": {"values": [1, 2]},
                "expected_output": 3,
            }
        ]
        serialized = detail.text
        assert HIDDEN_SENTINEL not in serialized
        assert SOLUTION_SENTINEL not in serialized
        assert INTERVIEWER_SENTINEL not in serialized
        assert "reference_solution" not in serialized
        assert "interviewer_instructions" not in serialized

        unpublished = client.get(
            "/api/v1/questions/unpublished-candidate-safe-cache", headers=headers
        )
        assert unpublished.status_code == 404
        cleanup_catalog_fixtures(engine)
