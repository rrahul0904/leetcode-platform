from __future__ import annotations

from typing import cast
from uuid import uuid4

from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from rigor_api.auth import LocalOIDCProvider
from rigor_api.main import app
from test_async_execution_http import _install_candidate_identity


def _auth(monkeypatch, *, prefix: str = "think") -> dict[str, str]:
    key = f"{prefix}-{uuid4().hex[:8]}"
    _install_candidate_identity(
        monkeypatch,
        key,
        f"local-{key}",
        f"{key}@rigor.test",
    )
    provider = cast(LocalOIDCProvider, app.state.local_oidc_provider)
    token = provider.issue_test_access_token(key, expires_in=900)
    return {"Authorization": f"Bearer {token}"}


def _idempotency(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex}"


def _create(
    client: TestClient,
    auth: dict[str, str],
    *,
    mode: str,
) -> dict[str, object]:
    response = client.post(
        "/api/v1/think-aloud/sessions",
        headers={**auth, "Idempotency-Key": _idempotency("create")},
        json={
            "focus": "system-design",
            "target_role": "Staff Software Engineer",
            "mode": mode,
        },
    )
    assert response.status_code == 201, response.text
    return cast(dict[str, object], response.json())


def test_think_aloud_routes_are_registered() -> None:
    routes = {
        (route.path, method)
        for route in app.routes
        if isinstance(route, APIRoute)
        for method in route.methods
    }
    expected = {
        ("/api/v1/think-aloud/sessions", "POST"),
        ("/api/v1/think-aloud/sessions/{session_id}", "GET"),
        ("/api/v1/think-aloud/sessions/{session_id}/turns/commit", "POST"),
        ("/api/v1/think-aloud/sessions/{session_id}/events", "POST"),
        ("/api/v1/think-aloud/sessions/{session_id}/canvas", "POST"),
        ("/api/v1/think-aloud/sessions/{session_id}/coaching", "POST"),
        ("/api/v1/think-aloud/sessions/{session_id}/coaching/resume", "POST"),
    }
    assert expected <= routes


def test_practice_mode_preserves_floor_canvas_and_coaching_state(monkeypatch) -> None:
    with TestClient(app) as client:
        auth = _auth(monkeypatch)
        created = _create(client, auth, mode="practice")
        session = cast(dict[str, object], created["session"])
        control = cast(dict[str, object], created["control"])
        session_id = str(session["id"])

        assert control["mode"] == "practice"
        assert control["floor_owner"] == "candidate"
        assert control["provider_connected"] is True

        silence = client.post(
            f"/api/v1/think-aloud/sessions/{session_id}/events",
            headers={**auth, "Idempotency-Key": _idempotency("silence")},
            json={"event_type": "candidate_silence", "payload": {"duration_ms": 7000}},
        )
        assert silence.status_code == 200, silence.text
        assert silence.json()["control"]["floor_owner"] == "candidate"

        canvas = client.post(
            f"/api/v1/think-aloud/sessions/{session_id}/canvas",
            headers={**auth, "Idempotency-Key": _idempotency("canvas")},
            json={
                "kind": "add_component",
                "label": "Notification API",
                "component_type": "service",
                "payload": {"notes": "Accept and validate requests"},
            },
        )
        assert canvas.status_code == 200, canvas.text
        assert len(canvas.json()["control"]["canvas"]) == 1
        assert canvas.json()["control"]["canvas"][0]["content"] == "Notification API"

        coached = client.post(
            f"/api/v1/think-aloud/sessions/{session_id}/coaching",
            headers={**auth, "Idempotency-Key": _idempotency("coach")},
            json={"question": "How should I structure the capacity discussion?"},
        )
        assert coached.status_code == 200, coached.text
        assert coached.json()["session"]["status"] == "PAUSED"
        assert coached.json()["control"]["coaching_active"] is True
        assert coached.json()["control"]["floor_owner"] == "coach"
        assert len(coached.json()["control"]["canvas"]) == 1

        resumed = client.post(
            f"/api/v1/think-aloud/sessions/{session_id}/coaching/resume",
            headers={**auth, "Idempotency-Key": _idempotency("resume")},
        )
        assert resumed.status_code == 200, resumed.text
        assert resumed.json()["session"]["status"] == "IN_PROGRESS"
        assert resumed.json()["control"]["coaching_active"] is False
        assert resumed.json()["control"]["floor_owner"] == "candidate"
        assert len(resumed.json()["control"]["canvas"]) == 1

        disconnected = client.post(
            f"/api/v1/think-aloud/sessions/{session_id}/events",
            headers={**auth, "Idempotency-Key": _idempotency("disconnect")},
            json={"event_type": "provider_disconnected", "payload": {"provider": "voice"}},
        )
        assert disconnected.status_code == 200
        assert disconnected.json()["control"]["provider_connected"] is False
        assert len(disconnected.json()["control"]["canvas"]) == 1

        reconnected = client.post(
            f"/api/v1/think-aloud/sessions/{session_id}/events",
            headers={**auth, "Idempotency-Key": _idempotency("reconnect")},
            json={"event_type": "provider_reconnected", "payload": {"provider": "voice"}},
        )
        assert reconnected.status_code == 200
        assert reconnected.json()["control"]["provider_connected"] is True


def test_assessment_disables_coaching_and_finalized_session_is_immutable(monkeypatch) -> None:
    with TestClient(app) as client:
        auth = _auth(monkeypatch, prefix="assessment")
        created = _create(client, auth, mode="assessment")
        session = cast(dict[str, object], created["session"])
        session_id = str(session["id"])

        denied = client.post(
            f"/api/v1/think-aloud/sessions/{session_id}/coaching",
            headers={**auth, "Idempotency-Key": _idempotency("coach-denied")},
            json={"question": "Give me a hint"},
        )
        assert denied.status_code == 409
        assert "disabled in assessment mode" in denied.json()["detail"]

        answers = [
            (
                "I would define functional delivery requirements, latency and availability SLA, "
                "estimate users and request scale, and state explicit scope assumptions."
            ),
            (
                "I would estimate QPS and peak burst headroom, storage and retention bytes, and "
                "state order of magnitude assumptions rather than false precision."
            ),
            (
                "Requests enter an API gateway and service, enqueue to Kafka, persist in a database "
                "with cache where useful, and workers consume for provider delivery with idempotency."
            ),
            (
                "I would use retry with exponential backoff and jitter, idempotency and deduplication, "
                "queue backpressure and throttling, circuit breakers, isolation, and a dead letter queue."
            ),
            (
                "I would operate with metrics traces and logs, SLO alerts and error budgets, canary deploys "
                "with rollback, incident runbooks and on-call response, while monitoring trade-offs."
            ),
        ]
        latest: dict[str, object] = created
        for index, answer in enumerate(answers):
            committed = client.post(
                f"/api/v1/think-aloud/sessions/{session_id}/turns/commit",
                headers={**auth, "Idempotency-Key": _idempotency(f"turn-{index}")},
                json={"content": answer},
            )
            assert committed.status_code == 200, committed.text
            latest = cast(dict[str, object], committed.json())

        latest_session = cast(dict[str, object], latest["session"])
        latest_control = cast(dict[str, object], latest["control"])
        assert latest_session["status"] == "COMPLETED"
        assert latest_session["report"] is not None
        assert latest_control["floor_owner"] == "none"

        immutable = client.post(
            f"/api/v1/think-aloud/sessions/{session_id}/canvas",
            headers={**auth, "Idempotency-Key": _idempotency("late-canvas")},
            json={
                "kind": "note",
                "label": "This must not be accepted after finalization",
                "payload": {},
            },
        )
        assert immutable.status_code == 409
        assert "immutable" in immutable.json()["detail"]
