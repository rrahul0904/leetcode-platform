from __future__ import annotations

from typing import cast
from uuid import uuid4

from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from rigor_api.auth import LocalOIDCProvider
from rigor_api.main import app
from sqlalchemy import Engine
from test_async_execution_http import _install_candidate_identity


def test_mock_interview_routes_are_registered_on_final_app() -> None:
    routes = {
        (route.path, method)
        for route in app.routes
        if isinstance(route, APIRoute)
        for method in route.methods
    }

    expected = {
        ("/api/v1/mock-interviews/templates", "GET"),
        ("/api/v1/mock-interviews", "POST"),
        ("/api/v1/mock-interviews", "GET"),
        ("/api/v1/mock-interviews/{session_id}", "GET"),
        ("/api/v1/mock-interviews/{session_id}/responses", "POST"),
        ("/api/v1/mock-interviews/{session_id}/actions", "POST"),
    }
    assert expected <= routes


def test_durable_mock_interview_completes_and_is_candidate_isolated(monkeypatch) -> None:
    other_key = f"mock-other-{uuid4().hex[:8]}"
    _install_candidate_identity(
        monkeypatch,
        other_key,
        f"local-{other_key}",
        f"{other_key}@rigor.test",
    )

    with TestClient(app) as client:
        provider = cast(LocalOIDCProvider, app.state.local_oidc_provider)
        engine = cast(Engine, app.state.database_engine)
        assert engine is not None

        token = provider.issue_test_access_token("candidate", expires_in=900)
        auth = {"Authorization": f"Bearer {token}"}
        create_key = f"mock-create-{uuid4().hex}"

        template_response = client.get(
            "/api/v1/mock-interviews/templates",
            headers=auth,
        )
        assert template_response.status_code == 200
        assert {
            item["slug"] for item in template_response.json()
        } >= {"data-engineering", "system-design", "ai-architecture"}

        created = client.post(
            "/api/v1/mock-interviews",
            headers={**auth, "Idempotency-Key": create_key},
            json={
                "focus": "data-engineering",
                "target_role": "Senior Data Engineer",
            },
        )
        assert created.status_code == 201, created.text
        session = created.json()
        session_id = session["id"]
        assert session["status"] == "IN_PROGRESS"
        assert session["current_phase"] == "problem-framing"
        assert session["messages"][0]["role"] == "interviewer"

        duplicate = client.post(
            "/api/v1/mock-interviews",
            headers={**auth, "Idempotency-Key": create_key},
            json={
                "focus": "data-engineering",
                "target_role": "Senior Data Engineer",
            },
        )
        assert duplicate.status_code == 201
        assert duplicate.json()["id"] == session_id

        conflict = client.post(
            "/api/v1/mock-interviews",
            headers={**auth, "Idempotency-Key": create_key},
            json={
                "focus": "data-engineering",
                "target_role": "Principal Data Engineer",
            },
        )
        assert conflict.status_code == 409

        paused = client.post(
            f"/api/v1/mock-interviews/{session_id}/actions",
            headers=auth,
            json={"action": "pause"},
        )
        assert paused.status_code == 200
        assert paused.json()["status"] == "PAUSED"

        resumed = client.post(
            f"/api/v1/mock-interviews/{session_id}/actions",
            headers=auth,
            json={"action": "resume"},
        )
        assert resumed.status_code == 200
        assert resumed.json()["status"] == "IN_PROGRESS"

        responses = [
            (
                "I would quantify volume and throughput, define latency and freshness SLA, "
                "identify each source producer and downstream consumer, and establish schema "
                "contracts plus data quality and accuracy requirements."
            ),
            (
                "I would use streaming through Kafka plus batch replay, land durable data in "
                "object storage and a warehouse or lakehouse, partition by time and domain, "
                "validate schema evolution, and make writes idempotent with deduplication."
            ),
            (
                "I would use retry with backoff and a DLQ, checkpoints and replay, queue-based "
                "backpressure, metrics alerts and tracing, plus failure isolation and degraded "
                "operation when the downstream warehouse is unavailable."
            ),
            (
                "I would balance cost and compute against latency and freshness, preserve "
                "correctness and consistency, limit operational complexity, and explicitly "
                "defer lower-value features into a later phase."
            ),
        ]

        latest = session
        for index, answer in enumerate(responses):
            response_key = f"mock-answer-{index}-{uuid4().hex}"
            answered = client.post(
                f"/api/v1/mock-interviews/{session_id}/responses",
                headers={**auth, "Idempotency-Key": response_key},
                json={"content": answer},
            )
            assert answered.status_code == 200, answered.text
            latest = answered.json()

        assert latest["status"] == "COMPLETED"
        assert latest["current_phase"] == "COMPLETE"
        assert latest["report"] is not None
        assert latest["report"]["overall_score"] >= 0.7
        assert len(latest["report"]["rubric_evidence"]) == 4
        assert latest["report"]["strengths"]

        history = client.get("/api/v1/mock-interviews", headers=auth)
        assert history.status_code == 200
        assert session_id in {item["id"] for item in history.json()}

        evidence = client.get("/api/v1/me/evidence", headers=auth)
        assert evidence.status_code == 200
        mock_evidence = [
            item
            for item in evidence.json()
            if item["source_type"] == "MOCK_INTERVIEW"
            and item["source_id"] == session_id
        ]
        assert len(mock_evidence) >= 3

        other_token = provider.issue_test_access_token(other_key, expires_in=900)
        other_auth = {"Authorization": f"Bearer {other_token}"}
        hidden = client.get(
            f"/api/v1/mock-interviews/{session_id}",
            headers=other_auth,
        )
        assert hidden.status_code == 404
