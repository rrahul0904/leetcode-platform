from __future__ import annotations

import json
from typing import cast

from fastapi.testclient import TestClient
from rigor_api.auth import LocalOIDCProvider
from rigor_api.main import app
from sqlalchemy import Engine, text
from test_async_execution_http import _candidate_context, _install_candidate_identity


def test_candidate_cannot_read_another_candidates_submission_or_evidence(monkeypatch) -> None:
    with TestClient(app) as client:
        engine, headers_a, slug, session_id = _candidate_context(client)
        provider = cast(LocalOIDCProvider, app.state.local_oidc_provider)
        _install_candidate_identity(
            monkeypatch,
            "candidate-submission-b",
            "local-candidate-submission-b",
            "candidate-submission-b@rigor.test",
        )
        token_b = provider.issue_test_access_token("candidate-submission-b", expires_in=900)
        headers_b = {"Authorization": f"Bearer {token_b}"}

        queued = client.post(
            f"/api/v1/questions/{slug}/submissions",
            headers={**headers_a, "Idempotency-Key": "submission-isolation-proof-0001"},
            json={
                "session_id": session_id,
                "source_code": "def solve(value):\n    return value\n",
                "runtime": "python3.13",
            },
        )
        assert queued.status_code == 202, queued.text
        submission_id = queued.json()["submission_id"]
        execution_id = queued.json()["execution_id"]

        with cast(Engine, engine).begin() as connection:
            candidate_id = connection.execute(
                text(
                    "SELECT candidate_id FROM execution_requests WHERE id=:execution_id"
                ),
                {"execution_id": execution_id},
            ).scalar_one()
            competency_id = connection.execute(
                text("SELECT id FROM competencies ORDER BY slug LIMIT 1")
            ).scalar_one()
            connection.execute(
                text(
                    """
                    UPDATE submissions
                    SET status='passed', completed_at=CURRENT_TIMESTAMP
                    WHERE id=:submission_id
                    """
                ),
                {"submission_id": submission_id},
            )
            connection.execute(
                text(
                    """
                    INSERT INTO submission_results(
                        submission_id, status, public_results, hidden_total,
                        hidden_passed, runtime_ms, memory_kb, error_category,
                        candidate_message, quality_signals
                    ) VALUES (
                        :submission_id, 'PASSED'::execution_state,
                        CAST(:public_results AS jsonb),
                        1, 1, 10, 1024, NULL, 'passed', '{}'::jsonb
                    )
                    """
                ),
                {
                    "submission_id": submission_id,
                    "public_results": json.dumps(
                        [
                            {
                                "id": "public-1",
                                "name": "identity",
                                "passed": True,
                                "expected_output": 7,
                                "actual_output": 7,
                            }
                        ]
                    ),
                },
            )
            connection.execute(
                text(
                    """
                    INSERT INTO submission_evaluations(
                        submission_id, correctness_score, complexity_score,
                        code_quality_score, testing_score, robustness_score,
                        overall_score, evaluator_version, deterministic_signals,
                        heuristic_signals
                    ) VALUES (
                        :submission_id, 1, 1, 1, 1, 1, 1,
                        'submission-isolation-test',
                        CAST(:deterministic_signals AS jsonb),
                        '{}'::jsonb
                    )
                    """
                ),
                {
                    "submission_id": submission_id,
                    "deterministic_signals": json.dumps(
                        {
                            "public_total": 1,
                            "public_passed": 1,
                            "hidden_total": 1,
                            "hidden_passed": 1,
                        }
                    ),
                },
            )
            connection.execute(
                text(
                    """
                    INSERT INTO candidate_competency_evidence(
                        organization_id, candidate_id, competency_id, source_type,
                        source_id, score, confidence, weight, evaluator_version,
                        observed_at, evidence
                    ) VALUES (
                        NULL, :candidate_id, :competency_id, 'CODING_SUBMISSION',
                        :source_id, 1, 0.8, 1, 'submission-isolation-test',
                        CURRENT_TIMESTAMP, CAST(:evidence AS jsonb)
                    )
                    """
                ),
                {
                    "candidate_id": candidate_id,
                    "competency_id": competency_id,
                    "source_id": str(submission_id),
                    "evidence": json.dumps({"proof": "candidate-a-only"}),
                },
            )

        b_list = client.get("/api/v1/submissions", headers=headers_b)
        assert b_list.status_code == 200, b_list.text
        assert submission_id not in {item["id"] for item in b_list.json()}

        b_get = client.get(f"/api/v1/submissions/{submission_id}", headers=headers_b)
        assert b_get.status_code == 404

        b_session = client.get(
            f"/api/v1/practice-sessions/{session_id}/submissions",
            headers=headers_b,
        )
        assert b_session.status_code == 404

        b_evidence = client.get("/api/v1/me/evidence", headers=headers_b)
        assert b_evidence.status_code == 200, b_evidence.text
        assert str(submission_id) not in {item["source_id"] for item in b_evidence.json()}

        a_list = client.get("/api/v1/submissions", headers=headers_a)
        assert a_list.status_code == 200, a_list.text
        assert submission_id in {item["id"] for item in a_list.json()}

        a_get = client.get(f"/api/v1/submissions/{submission_id}", headers=headers_a)
        assert a_get.status_code == 200, a_get.text
        assert a_get.json()["id"] == submission_id

        a_evidence = client.get("/api/v1/me/evidence", headers=headers_a)
        assert a_evidence.status_code == 200, a_evidence.text
        assert str(submission_id) in {item["source_id"] for item in a_evidence.json()}
