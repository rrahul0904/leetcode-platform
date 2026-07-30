from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import NoReturn, cast

from fastapi.testclient import TestClient
from rigor_api import submissions
from rigor_api.auth import LOCAL_IDENTITIES, ROLE_PERMISSIONS, LocalIdentity, LocalOIDCProvider
from rigor_api.database import principal_transaction
from rigor_api.main import app
from rigor_api.schemas import AuthenticatedPrincipal, Role
from sqlalchemy import Engine, create_engine, text

TEST_EXTERNAL_ID = "ASYNC-HTTP-0001"
TEST_SLUG = "async-http-execution-proof"
SQL_EXTERNAL_ID = "ASYNC-SQL-0001"
SQL_SLUG = "async-sql-execution-proof"


def _seed_published_question(
    engine: Engine,
    *,
    external_id: str,
    slug: str,
    title: str,
    structured_content: dict[str, object],
) -> str:
    with engine.begin() as connection:
        existing = connection.execute(
            text("SELECT slug FROM questions WHERE external_id=:external_id"),
            {"external_id": external_id},
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
                    :question_id, '1.0.0', :title,
                    'Execution contract proof.', 'advanced', 'advanced',
                    1, 1, 1, 1, 1, 15, 'published'::content_state,
                    CAST(:structured_content AS jsonb), :content_hash, 'async-http-test'
                )
                RETURNING id
                """
            ),
            {
                "question_id": question_id,
                "title": title,
                "structured_content": json.dumps(structured_content),
                "content_hash": external_id.casefold().encode("utf-8").hex().ljust(64, "0")[:64],
            },
        ).scalar_one()
        connection.execute(
            text(
                "UPDATE questions SET current_published_version_id=:version_id "
                "WHERE id=:question_id"
            ),
            {"version_id": version_id, "question_id": question_id},
        )
    return slug


def _seed_published_python_question(engine: Engine) -> str:
    return _seed_published_question(
        engine,
        external_id=TEST_EXTERNAL_ID,
        slug=TEST_SLUG,
        title="Async Execution Proof",
        structured_content={
            "learning_objectives": ["Prove asynchronous execution routing"],
            "prerequisites": ["Python functions"],
            "candidate_instructions": ["Return the supplied value"],
            "constraints": ["Use the provided function"],
            "interviewer_instructions": [],
            "strong_answer_indicators": [],
            "mode_specification": {
                "runtime": "3.13",
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
        },
    )


def _seed_published_sql_question(engine: Engine) -> str:
    return _seed_published_question(
        engine,
        external_id=SQL_EXTERNAL_ID,
        slug=SQL_SLUG,
        title="Async SQL Execution Proof",
        structured_content={
            "question_type": "sql_coding",
            "learning_objectives": ["Prove isolated PostgreSQL execution routing"],
            "prerequisites": ["SQL"],
            "candidate_instructions": ["Return department counts"],
            "constraints": ["PostgreSQL 18"],
            "interviewer_instructions": [],
            "strong_answer_indicators": [],
            "mode_specification": {
                "dialect": "postgresql",
                "business_problem": "Count employees per department.",
                "ddl": (
                    "CREATE TABLE employees ("
                    "id integer PRIMARY KEY, department text NOT NULL);"
                ),
                "seed_data": (
                    "INSERT INTO employees (id, department) VALUES "
                    "(1, 'AI'), (2, 'AI'), (3, 'Data');"
                ),
                "statement_timeout_ms": 1_000,
                "tests": [
                    {
                        "id": "public-sql-1",
                        "name": "department counts",
                        "visibility": "public",
                        "input": None,
                        "expected_output": [
                            {"department": "AI", "employees": 2},
                            {"department": "Data", "employees": 1},
                        ],
                        "comparison": "ordered",
                    },
                    {
                        "id": "hidden-sql-1",
                        "name": "hidden department fixture",
                        "visibility": "hidden",
                        "input": {
                            "setup_sql": (
                                "INSERT INTO employees (id, department) VALUES (4, 'AI');"
                            )
                        },
                        "expected_output": [
                            {"department": "AI", "employees": 3},
                            {"department": "Data", "employees": 1},
                        ],
                        "comparison": "ordered",
                    },
                ],
            },
        },
    )


def _candidate_context(client: TestClient) -> tuple[Engine, dict[str, str], str, str]:
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
    return engine, auth, slug, session_response.json()["id"]


def _install_candidate_identity(monkeypatch, key: str, subject: str, email: str) -> LocalIdentity:
    identity = LocalIdentity(subject, email, key.replace("-", " ").title(), (Role.candidate,))
    monkeypatch.setitem(LOCAL_IDENTITIES, key, identity)
    return identity


def _principal(identity: LocalIdentity, correlation_id: str) -> AuthenticatedPrincipal:
    permissions: set[str] = set()
    for role in identity.roles:
        permissions.update(ROLE_PERMISSIONS[role])
    return AuthenticatedPrincipal(
        subject_id=identity.subject_id,
        email=identity.email,
        display_name=identity.display_name,
        organization_id=None,
        roles=list(identity.roles),
        permissions=sorted(permissions),
        authentication_provider="local-oidc",
        token_issued_at=datetime.now(UTC),
        correlation_id=correlation_id,
    )


def test_http_run_is_queued_transactionally_without_fastapi_execution(monkeypatch) -> None:
    def forbidden_local_execution(*args: object, **kwargs: object) -> NoReturn:
        del args, kwargs
        raise AssertionError("FastAPI attempted to execute untrusted candidate code locally")

    monkeypatch.setattr(submissions.RUNNER, "execute", forbidden_local_execution)

    with TestClient(app) as client:
        engine, auth, slug, session_id = _candidate_context(client)
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
        assert body["execution_type"] == "RUN"
        assert body["attempt"] == 0
        assert body["submission_id"] is None
        execution_id = body["execution_id"]
        assert body["status_url"] == f"/api/v1/executions/{execution_id}"

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
        assert all("expected" not in test for test in execution["input_payload"]["tests"])

        status_response = client.get(
            f"/api/v1/executions/{execution_id}",
            headers=auth,
        )
        assert status_response.status_code == 200
        assert status_response.json()["status"] == "QUEUED"
        assert status_response.json()["attempt"] == 0
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
            json={
                "session_id": session_id,
                "source_code": "def solve(value): return value + 1",
            },
        )
        assert conflict.status_code == 409


def test_sql_run_uses_same_async_service_and_trusted_runtime(monkeypatch) -> None:
    identity = _install_candidate_identity(
        monkeypatch,
        "sql-candidate",
        "local-sql-candidate",
        "sql-candidate@rigor.test",
    )
    del identity

    with TestClient(app) as client:
        engine = cast(Engine, app.state.database_engine)
        provider = cast(LocalOIDCProvider, app.state.local_oidc_provider)
        slug = _seed_published_sql_question(engine)
        token = provider.issue_test_access_token("sql-candidate", expires_in=900)
        auth = {"Authorization": f"Bearer {token}"}

        wrong_runtime = client.post(
            "/api/v1/practice-sessions",
            headers=auth,
            json={"question_slug": slug, "runtime": "python3.13"},
        )
        assert wrong_runtime.status_code == 409

        session_response = client.post(
            "/api/v1/practice-sessions",
            headers=auth,
            json={"question_slug": slug, "runtime": "postgresql18"},
        )
        assert session_response.status_code == 201, session_response.text
        session_id = session_response.json()["id"]
        source = (
            "SELECT department, count(*) AS employees FROM employees "
            "GROUP BY department ORDER BY department"
        )
        run = client.post(
            f"/api/v1/questions/{slug}/run",
            headers={**auth, "Idempotency-Key": "sql-run-proof-0001"},
            json={"session_id": session_id, "source_code": source},
        )
        assert run.status_code == 202, run.text
        execution_id = run.json()["execution_id"]

        with engine.connect() as connection:
            row = (
                connection.execute(
                    text(
                        """
                        SELECT er.runtime, er.language, er.limits,
                               ep.input_payload, eo.payload AS outbox_payload
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
        assert row["runtime"] == "postgresql18"
        assert row["language"] == "sql"
        assert row["limits"]["profile"] == "sql-small"
        assert "CREATE TABLE employees" in row["input_payload"]["schema_sql"]
        assert all("expected" not in test for test in row["input_payload"]["tests"])
        assert source not in json.dumps(row["outbox_payload"])


def test_http_submit_uses_same_durable_execution_service(monkeypatch) -> None:
    def forbidden_local_execution(*args: object, **kwargs: object) -> NoReturn:
        del args, kwargs
        raise AssertionError("FastAPI attempted to execute submitted candidate code locally")

    monkeypatch.setattr(submissions.RUNNER, "execute", forbidden_local_execution)

    with TestClient(app) as client:
        engine, auth, slug, session_id = _candidate_context(client)
        source = "def solve(value):\n    return value\n"
        response = client.post(
            f"/api/v1/questions/{slug}/submissions",
            headers={**auth, "Idempotency-Key": "http-async-submit-proof-0001"},
            json={
                "session_id": session_id,
                "source_code": source,
                "runtime": "python3.13",
            },
        )

        assert response.status_code == 202, response.text
        body = response.json()
        assert body["execution_type"] == "SUBMIT"
        assert body["status"] == "QUEUED"
        assert body["attempt"] == 0
        assert body["submission_id"]
        execution_id = body["execution_id"]

        with engine.connect() as connection:
            row = (
                connection.execute(
                    text(
                        """
                        SELECT er.submission_id,
                               er.state::text AS execution_state,
                               s.status AS submission_status,
                               eo.payload AS outbox_payload
                        FROM execution_requests er
                        JOIN submissions s ON s.id=er.submission_id
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
        assert str(row["submission_id"]) == body["submission_id"]
        assert row["execution_state"] == "QUEUED"
        assert row["submission_status"] == "queued"
        assert source not in json.dumps(row["outbox_payload"])


def test_cross_candidate_execution_is_hidden_by_app_role_rls(monkeypatch) -> None:
    identity_a = _install_candidate_identity(
        monkeypatch,
        "rls-candidate-a",
        "local-rls-candidate-a",
        "rls-candidate-a@rigor.test",
    )
    identity_b = _install_candidate_identity(
        monkeypatch,
        "rls-candidate-b",
        "local-rls-candidate-b",
        "rls-candidate-b@rigor.test",
    )

    with TestClient(app) as client:
        fixture_engine = cast(Engine, app.state.database_engine)
        provider = cast(LocalOIDCProvider, app.state.local_oidc_provider)
        slug = _seed_published_python_question(fixture_engine)
        token_a = provider.issue_test_access_token("rls-candidate-a", expires_in=900)
        token_b = provider.issue_test_access_token("rls-candidate-b", expires_in=900)
        auth_a = {"Authorization": f"Bearer {token_a}"}
        auth_b = {"Authorization": f"Bearer {token_b}"}

        session = client.post(
            "/api/v1/practice-sessions",
            headers=auth_a,
            json={"question_slug": slug, "runtime": "python3.13"},
        )
        assert session.status_code == 201
        submission = client.post(
            f"/api/v1/questions/{slug}/submissions",
            headers={**auth_a, "Idempotency-Key": "rls-submit-proof-0001"},
            json={
                "session_id": session.json()["id"],
                "source_code": "def solve(value): return value",
                "runtime": "python3.13",
            },
        )
        assert submission.status_code == 202
        execution_id = submission.json()["execution_id"]
        submission_id = submission.json()["submission_id"]

        with fixture_engine.begin() as admin:
            admin.execute(
                text(
                    """
                    INSERT INTO execution_public_results (
                        execution_request_id, public_results, hidden_total,
                        hidden_passed, stdout, stderr, candidate_message
                    ) VALUES (
                        :execution_id, '[]'::jsonb, 1, 0, '', '', 'private result'
                    )
                    ON CONFLICT (execution_request_id) DO NOTHING
                    """
                ),
                {"execution_id": execution_id},
            )

        app_role_url = fixture_engine.url.set(
            username="rigor_app",
            password="rigor_app_local_only",
        )
        app_role_engine = create_engine(app_role_url, pool_pre_ping=True)
        principal_b = _principal(identity_b, "rls-direct-candidate-b")
        try:
            app.state.database_engine = app_role_engine
            forbidden_get = client.get(
                f"/api/v1/executions/{execution_id}",
                headers=auth_b,
            )
            forbidden_cancel = client.post(
                f"/api/v1/executions/{execution_id}/cancel",
                headers=auth_b,
            )
            assert forbidden_get.status_code == 404
            assert forbidden_cancel.status_code == 404

            with principal_transaction(app_role_engine, principal_b) as connection:
                counts = {
                    "execution": connection.execute(
                        text("SELECT count(*) FROM execution_requests WHERE id=:id"),
                        {"id": execution_id},
                    ).scalar_one(),
                    "payload": connection.execute(
                        text(
                            "SELECT count(*) FROM execution_payloads "
                            "WHERE execution_request_id=:id"
                        ),
                        {"id": execution_id},
                    ).scalar_one(),
                    "events": connection.execute(
                        text(
                            "SELECT count(*) FROM execution_events "
                            "WHERE execution_request_id=:id"
                        ),
                        {"id": execution_id},
                    ).scalar_one(),
                    "outbox": connection.execute(
                        text("SELECT count(*) FROM execution_outbox WHERE aggregate_id=:id"),
                        {"id": execution_id},
                    ).scalar_one(),
                    "result": connection.execute(
                        text(
                            "SELECT count(*) FROM execution_public_results "
                            "WHERE execution_request_id=:id"
                        ),
                        {"id": execution_id},
                    ).scalar_one(),
                    "submission": connection.execute(
                        text("SELECT count(*) FROM submissions WHERE id=:id"),
                        {"id": submission_id},
                    ).scalar_one(),
                }
            assert counts == {
                "execution": 0,
                "payload": 0,
                "events": 0,
                "outbox": 0,
                "result": 0,
                "submission": 0,
            }
        finally:
            app.state.database_engine = fixture_engine
            app_role_engine.dispose()

        assert identity_a.subject_id != identity_b.subject_id


def test_execution_http_surface_authenticates_before_execution_work(monkeypatch) -> None:
    def forbidden_local_execution(*args: object, **kwargs: object) -> NoReturn:
        del args, kwargs
        raise AssertionError("public execution surface reached LocalFunctionalPythonRunner")

    monkeypatch.setattr(submissions.RUNNER, "execute", forbidden_local_execution)
    execution_id = "11111111-2222-3333-4444-555555555555"

    with TestClient(app) as client:
        run = client.post(
            "/api/v1/questions/anything/run",
            headers={"Idempotency-Key": "unauthenticated-run-proof-0001"},
            json={
                "session_id": execution_id,
                "source_code": "def solve(value): return value",
            },
        )
        submit = client.post(
            "/api/v1/questions/anything/submissions",
            headers={"Idempotency-Key": "unauthenticated-submit-proof-0001"},
            json={
                "session_id": execution_id,
                "source_code": "def solve(value): return value",
                "runtime": "python3.13",
            },
        )
        status_response = client.get(f"/api/v1/executions/{execution_id}")
        cancel = client.post(f"/api/v1/executions/{execution_id}/cancel")

    assert run.status_code == 401
    assert submit.status_code == 401
    assert status_response.status_code == 401
    assert cancel.status_code == 401
