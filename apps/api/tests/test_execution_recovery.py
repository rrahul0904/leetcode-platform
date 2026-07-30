from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import cast
from uuid import uuid4

from fastapi.testclient import TestClient
from rigor_api.auth import LocalOIDCProvider
from rigor_api.execution_claims import ExecutionClaimRepository
from rigor_api.main import app
from sqlalchemy import Engine, text

RECOVERY_EXTERNAL_ID = "EXEC-RECOVERY-0001"
RECOVERY_SLUG = "execution-recovery-proof"


def _seed_recovery_question(engine: Engine) -> str:
    structured = {
        "learning_objectives": ["Prove durable execution recovery"],
        "prerequisites": ["Python functions"],
        "candidate_instructions": ["Return the input"],
        "constraints": [],
        "interviewer_instructions": [],
        "strong_answer_indicators": [],
        "mode_specification": {
            "runtime": "3.13",
            "starter_code": "def solve(value):\n    return value\n",
            "entrypoint": "solve",
            "tests": [
                {
                    "id": "public-1",
                    "name": "identity",
                    "visibility": "public",
                    "input": 7,
                    "expected_output": 7,
                }
            ],
        },
    }
    with engine.begin() as connection:
        existing = connection.execute(
            text("SELECT slug FROM questions WHERE external_id=:external_id"),
            {"external_id": RECOVERY_EXTERNAL_ID},
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
                "external_id": RECOVERY_EXTERNAL_ID,
                "slug": RECOVERY_SLUG,
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
                    :question_id, '1.0.0', 'Execution Recovery Proof',
                    'Return the supplied value.', 'advanced', 'advanced',
                    1, 1, 1, 1, 1, 15, 'published'::content_state,
                    CAST(:structured AS jsonb), :content_hash, 'recovery-test'
                )
                RETURNING id
                """
            ),
            {
                "question_id": question_id,
                "structured": json.dumps(structured),
                "content_hash": "c" * 64,
            },
        ).scalar_one()
        connection.execute(
            text(
                "UPDATE questions SET current_published_version_id=:version_id "
                "WHERE id=:question_id"
            ),
            {"version_id": version_id, "question_id": question_id},
        )
    return RECOVERY_SLUG


def _queue_execution(client: TestClient) -> tuple[Engine, str]:
    engine = cast(Engine, app.state.database_engine)
    provider = cast(LocalOIDCProvider, app.state.local_oidc_provider)
    slug = _seed_recovery_question(engine)
    token = provider.issue_test_access_token("candidate", expires_in=900)
    auth = {"Authorization": f"Bearer {token}"}
    session = client.post(
        "/api/v1/practice-sessions",
        headers=auth,
        json={"question_slug": slug, "runtime": "python3.13"},
    )
    assert session.status_code == 201, session.text
    queued = client.post(
        f"/api/v1/questions/{slug}/run",
        headers={**auth, "Idempotency-Key": f"recovery-{uuid4()}"},
        json={
            "session_id": session.json()["id"],
            "source_code": "def solve(value): return value",
        },
    )
    assert queued.status_code == 202, queued.text
    return engine, queued.json()["execution_id"]


def test_at_least_once_delivery_has_single_atomic_claim_winner() -> None:
    with TestClient(app) as client:
        engine, execution_id = _queue_execution(client)
        lease = datetime.now(UTC) + timedelta(minutes=1)
        with engine.begin() as connection:
            repository = ExecutionClaimRepository(connection)
            first = repository.claim_for_dispatch(
                execution_id,
                worker_id="worker-a",
                lease_expires_at=lease,
            )
            duplicate = repository.claim_for_dispatch(
                execution_id,
                worker_id="worker-b",
                lease_expires_at=lease,
            )

        assert first is not None
        assert first.attempt_count == 1
        assert duplicate is None


def test_expired_missing_sandbox_creates_new_attempt_and_fences_old_worker() -> None:
    with TestClient(app) as client:
        engine, execution_id = _queue_execution(client)
        initial_lease = datetime.now(UTC) + timedelta(minutes=1)
        with engine.begin() as connection:
            repository = ExecutionClaimRepository(connection)
            first = repository.claim_for_dispatch(
                execution_id,
                worker_id="worker-a",
                lease_expires_at=initial_lease,
            )
            assert first is not None
            assert repository.mark_running(
                execution_id,
                worker_id="worker-a",
                kubernetes_namespace="rigor-execution",
                kubernetes_job_name=f"execution-{execution_id}",
            )
            assert not repository.lock_owned_attempt(
                execution_id,
                worker_id="worker-b",
                attempt_count=1,
            )

        with engine.begin() as connection:
            connection.execute(
                text(
                    """
                    UPDATE execution_requests
                    SET lease_expires_at=CURRENT_TIMESTAMP - INTERVAL '1 second'
                    WHERE id=:execution_id
                    """
                ),
                {"execution_id": execution_id},
            )

        retry_lease = datetime.now(UTC) + timedelta(minutes=1)
        with engine.begin() as connection:
            repository = ExecutionClaimRepository(connection)
            attempt = repository.retry_missing_sandbox(
                execution_id,
                expected_attempt=1,
                worker_id="worker-b",
                lease_expires_at=retry_lease,
                max_attempts=3,
            )
            assert attempt == 2
            assert not repository.lock_owned_attempt(
                execution_id,
                worker_id="worker-a",
                attempt_count=1,
            )
            assert repository.lock_owned_attempt(
                execution_id,
                worker_id="worker-b",
                attempt_count=2,
            )
            row = connection.execute(
                text(
                    """
                    SELECT state::text AS state, attempt_count, lease_owner,
                           kubernetes_namespace, kubernetes_job_name
                    FROM execution_requests
                    WHERE id=:execution_id
                    """
                ),
                {"execution_id": execution_id},
            ).mappings().one()

        assert row["state"] == "DISPATCHING"
        assert row["attempt_count"] == 2
        assert row["lease_owner"] == "worker-b"
        assert row["kubernetes_namespace"] is None
        assert row["kubernetes_job_name"] is None


def test_retry_exhaustion_cannot_create_attempt_beyond_server_bound() -> None:
    with TestClient(app) as client:
        engine, execution_id = _queue_execution(client)
        with engine.begin() as connection:
            connection.execute(
                text(
                    """
                    UPDATE execution_requests
                    SET state='RUNNING'::execution_state,
                        attempt_count=3,
                        lease_owner='worker-a',
                        lease_expires_at=CURRENT_TIMESTAMP - INTERVAL '1 second'
                    WHERE id=:execution_id
                    """
                ),
                {"execution_id": execution_id},
            )

        with engine.begin() as connection:
            attempt = ExecutionClaimRepository(connection).retry_missing_sandbox(
                execution_id,
                expected_attempt=3,
                worker_id="worker-b",
                lease_expires_at=datetime.now(UTC) + timedelta(minutes=1),
                max_attempts=3,
            )
            durable_attempt = connection.execute(
                text("SELECT attempt_count FROM execution_requests WHERE id=:execution_id"),
                {"execution_id": execution_id},
            ).scalar_one()

        assert attempt is None
        assert durable_attempt == 3
