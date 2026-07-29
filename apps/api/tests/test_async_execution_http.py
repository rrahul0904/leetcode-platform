from __future__ import annotations

from typing import NoReturn, cast

from fastapi.testclient import TestClient
from rigor_api import submissions
from rigor_api.auth import LocalOIDCProvider
from rigor_api.main import app
from sqlalchemy import Engine, text


def _published_python_question(engine: Engine) -> str:
    with engine.connect() as connection:
        slug = connection.execute(
            text(
                """
                SELECT q.slug
                FROM questions q
                JOIN question_versions v ON v.id=q.current_published_version_id
                WHERE v.state='published'::content_state
                  AND jsonb_typeof(
                    v.structured_content->'mode_specification'->'tests'
                  )='array'
                  AND jsonb_array_length(
                    v.structured_content->'mode_specification'->'tests'
                  ) > 0
                ORDER BY q.slug
                LIMIT 1
                """
            )
        ).scalar_one_or_none()
    assert isinstance(slug, str), "seeded CI database needs an executable Python question"
    return slug


def test_http_run_is_queued_transactionally_without_fastapi_execution(monkeypatch) -> None:
    def forbidden_local_execution(*args: object, **kwargs: object) -> NoReturn:
        del args, kwargs
        raise AssertionError("FastAPI attempted to execute untrusted candidate code locally")

    monkeypatch.setattr(submissions.RUNNER, "execute", forbidden_local_execution)

    with TestClient(app) as client:
        engine = cast(Engine, app.state.database_engine)
        provider = cast(LocalOIDCProvider, app.state.local_oidc_provider)
        token = provider.issue_test_access_token("candidate", expires_in=900)
        auth = {"Authorization": f"Bearer {token}"}
        slug = _published_python_question(engine)

        session_response = client.post(
            "/api/v1/practice-sessions",
            headers=auth,
            json={"question_slug": slug, "runtime": "python3.13"},
        )
        assert session_response.status_code == 201, session_response.text
        session_id = session_response.json()["id"]

        response = client.post(
            "/api/v1/executions/run",
            headers={
                **auth,
                "Idempotency-Key": "http-async-run-proof-0001",
                "X-Rigor-Question-Slug": slug,
            },
            json={
                "session_id": session_id,
                "source_code": "def solve(value):\n    return value\n",
            },
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
                               ep.source_code,
                               eo.event_type,
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
        assert execution["source_code"].startswith("def solve")
        assert execution["event_type"] == "execution.requested"
        assert execution["published_at"] is None

        status_response = client.get(
            f"/api/v1/executions/{execution_id}",
            headers=auth,
        )
        assert status_response.status_code == 200
        assert status_response.json()["status"] == "QUEUED"
        assert status_response.json()["result"] is None


def test_legacy_http_run_is_fail_closed_before_local_runner(monkeypatch) -> None:
    def forbidden_local_execution(*args: object, **kwargs: object) -> NoReturn:
        del args, kwargs
        raise AssertionError("legacy route reached LocalFunctionalPythonRunner")

    monkeypatch.setattr(submissions.RUNNER, "execute", forbidden_local_execution)

    with TestClient(app) as client:
        response = client.post("/api/v1/questions/anything/run", json={})

    assert response.status_code == 410
    assert "Synchronous candidate execution is disabled" in response.json()["detail"]
