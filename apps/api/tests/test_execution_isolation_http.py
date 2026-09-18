from __future__ import annotations

from typing import cast

from fastapi.testclient import TestClient
from rigor_api.auth import LocalOIDCProvider
from rigor_api.main import app
from sqlalchemy import Engine, text
from test_async_execution_http import _candidate_context, _install_candidate_identity


def test_candidate_cannot_read_or_cancel_another_candidates_execution(monkeypatch) -> None:
    with TestClient(app) as client:
        engine, headers_a, slug, session_id = _candidate_context(client)
        provider = cast(LocalOIDCProvider, app.state.local_oidc_provider)
        _install_candidate_identity(
            monkeypatch,
            "candidate-execution-b",
            "local-candidate-execution-b",
            "candidate-execution-b@rigor.test",
        )
        token_b = provider.issue_test_access_token("candidate-execution-b", expires_in=900)
        headers_b = {"Authorization": f"Bearer {token_b}"}

        queued = client.post(
            f"/api/v1/questions/{slug}/run",
            headers={**headers_a, "Idempotency-Key": "execution-isolation-run-0001"},
            json={
                "session_id": session_id,
                "source_code": "def solve(value):\n    return value\n",
            },
        )
        assert queued.status_code == 202, queued.text
        execution_id = queued.json()["execution_id"]

        forbidden_read = client.get(
            f"/api/v1/executions/{execution_id}",
            headers=headers_b,
        )
        assert forbidden_read.status_code == 404

        forbidden_cancel = client.post(
            f"/api/v1/executions/{execution_id}/cancel",
            headers=headers_b,
        )
        assert forbidden_cancel.status_code == 404

        owner_read = client.get(
            f"/api/v1/executions/{execution_id}",
            headers=headers_a,
        )
        assert owner_read.status_code == 200, owner_read.text
        assert owner_read.json()["status"] == "QUEUED"

        with cast(Engine, engine).connect() as connection:
            persisted_state = connection.execute(
                text(
                    "SELECT state::text FROM execution_requests WHERE id=:execution_id"
                ),
                {"execution_id": execution_id},
            ).scalar_one()
        assert persisted_state == "QUEUED"
