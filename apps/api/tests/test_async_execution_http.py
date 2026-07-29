from __future__ import annotations

import json
from typing import NoReturn, cast

from fastapi.testclient import TestClient
from rigor_api import submissions
from rigor_api.auth import LocalOIDCProvider
from rigor_api.main import app
from sqlalchemy import Engine, text

TEST_EXTERNAL_ID = "ASYNC-HTTP-0001"
TEST_SLUG = "async-http-execution-proof"


def _seed_published_python_question(engine: Engine) -> str:
    structured_content = {
        "learning_objectives": ["Prove asynchronous execution routing"],
        "prerequisites": ["Python functions"],
        "candidate_instructions": ["Return the supplied value"],
        "constraints": ["Use the provided function"],
        "interviewer_instructions": [],
        "strong_answer_indicators": [],
        "mode_specification": {
            "starter_code": "def solve(value):\n    return value\n",
            "entrypoint": "solve",
            "tests": [
                {
                    "id": "public-1",
                    "name": "public identity",
                    "visibility": "public",
                    "input": 7,
                    "expected_output": 7,
                },
                {
                    "id": "hidden-1",
                    "name": "hidden identity",
                    "visibility": "hidden",
                    "input": 41,
                    "expected_output": 41,
                },
            ],
        },
    }
    with engine.begin() as connection:
        existing = connection.execute(
            text("SELECT slug FROM questions WHERE external_id=:external_id"),
            {"external_id": TEST_EXTERNAL_ID},
        ).scalar_one_or_none()
        if isinstance(existing, str):
            return existing

        track_id = connection.execute(
            text("SELECT id FROM question_tracks WHERE slug='python-engineering'")
        ).scalar_one()
        question_id = connection.execute(
            text(
                """
                INSERT INTO questions (external_id, slug, primary_track_id)
                VALUES (:external_id, :slug, :track_id)
                RETURNING id
                """
            ),
            {
                "external_id": TEST_EXTERNAL_ID,
                "slug": TEST_SLUG,
                "track_id": track_id,
            },
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
                    :question_id, '1.0.0', 'Async Execution Proof',
                    'Return the supplied value.', 'advanced', 'advanced',
                    1, 1, 1, 1, 1, 15, 'published'::content_state,
                    CAST(:structured_content AS jsonb), :content_hash, 'async-http-test'
                )
                RETURNING id
                """
            ),
            {
                "question_id": question_id,
                "structured_content": json.dumps(structured_content),
                "content_hash": "b" * 64,
            },
        ).scalar_one()
        connection.execute(
            text(
                "UPDATE questions SET current_published_version_id=:version_id WHERE id=:question_id"
            ),
            {"version_id": version_id, "question_id": question_id},
        )
    return TEST_SLUG


def test_http_run_is_queued_transactionally_without_fastapi_execution(monkeypatch) -> None:
    def forbidden_local_execution(*args: object, **kwargs: object) -> NoReturn:
        del args, kwargs
        raise AssertionError("FastAPI attempted to execute untrusted candidate code locally")

    monkeypatch.setattr(submissions.RUNNER, "execute", forbidden_local_execution)

    with TestClient(app) as client:
        engine = cast(Engine, app.state.database_engine)
        provider = cast(LocalOIDCProvider, app.state.local_oidc_provider)
        slug = _seed_published_python_question(engine)
        token = provider.issue_test_access_token("candidate", expires_in=900)
        auth = {"Authorization": f"Bearer {token}"}

        session_response = client.post(
            "/api/v1/practice-sessions",
            headers=auth,
            json={"question_slug": slug, "runtime": "python3.13"},
        )
        assert session_response.status_code == 201, session_response.text
        session_id = session_response.json()["id"]
        key = "http-async-run-proof-0001"
        source = "def solve(value):\n    return value\n"

        response = client.post(
            f"/api/v1/questions/{slug}/run",
            headers={**auth, "Idempotency-Key": key},
            json={"session_id": session_id, "source_code": source},
        )

        assert response.status_code == 202, response.text
        body = response.json()
        assert body["status"] == "QUEUED"
        assert body["submission_id"] is None
        execution_id = body["execution_id"]

        with engine.connect() as connection:
            execution = (
                connection.execute(
                    text(
                        """
                        SELECT er.state::text AS state,
                               er.execution_type,
                               er.attempt_count,
                               ep.source_code,
                               ep.input_payload,
                               eo.event_type,
                               eo.payload AS outbox_payload,
                               eo.published_at
                        FROM execution_requests er
                        JOIN execution_payloads ep ON ep.execution_request_id=er.id
                        JOIN execution_outbox eo ON eo.aggregate_id=er.id
                        WHERE er.id=:execution_id
                          AND eo.event_type='execution.requested'
                        """
                    ),
                    {"execution_id": execution_id},
                )
                .mappings()
                .one()
            )
        assert execution["state"] == "QUEUED"
        assert execution["execution_type"] == "RUN"
        assert execution["attempt_count"] == 0
        assert execution["source_code"] == source
        assert execution["event_type"] == "execution.requested"
        assert execution["published_at"] is None
        assert "source_code" not in execution["outbox_payload"]
        assert source not in json.dumps(execution["outbox_payload"])
        assert all(
            "expected" not in test
            for test in execution["input_payload"]["tests"]
        )

        status_response = client.get(
            f"/api/v1/executions/{execution_id}",
            headers=auth,
        )
        assert status_response.status_code == 200
        assert status_response.json()["status"] == "QUEUED"
        assert status_response.json()["result"] is None

        duplicate = client.post(
            f"/api/v1/questions/{slug}/run",
            headers={**auth, "Idempotency-Key": key},
            json={"session_id": session_id, "source_code": source},
        )
        assert duplicate.status_code == 202
        assert duplicate.json()["execution_id"] == execution_id
        assert duplicate.json()["duplicate"] is True

        conflict = client.post(
            f"/api/v1/questions/{slug}/run",
            headers={**auth, "Idempotency-Key": key},
            json={"session_id": session_id, "source_code": "def solve(value): return value + 1"},
        )
        assert conflict.status_code == 409


def test_public_run_route_authenticates_before_any_execution_work(monkeypatch) -> None:
    def forbidden_local_execution(*args: object, **kwargs: object) -> NoReturn:
        del args, kwargs
        raise AssertionError("public route reached LocalFunctionalPythonRunner")

    monkeypatch.setattr(submissions.RUNNER, "execute", forbidden_local_execution)

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/questions/anything/run",
            headers={"Idempotency-Key": "unauthenticated-proof-0001"},
            json={
                "session_id": "11111111-2222-3333-4444-555555555555",
                "source_code": "def solve(value): return value",
            },
        )

    assert response.status_code == 401
