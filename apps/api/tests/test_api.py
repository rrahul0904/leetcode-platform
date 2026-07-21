from fastapi.testclient import TestClient
from rigor_api.main import app


def test_health_and_manifest_contract() -> None:
    with TestClient(app) as client:
        live = client.get("/livez")
        assert live.status_code == 200
        assert live.json() == {"status": "ok", "service": "rigor-api"}
        assert live.headers["x-correlation-id"]

        stats = client.get("/api/v1/content/stats")
        assert stats.status_code == 200
        payload = stats.json()
        assert payload["foundation_manifest_entries"] == 1350
        assert payload["growth_model"] == "continuous_unbounded"
        assert "target_questions" not in payload
        assert payload["planned_questions"] == 1350
        assert payload["published_questions"] == 0


def test_manifest_search_and_pagination() -> None:
    with TestClient(app) as client:
        response = client.get(
            "/api/v1/manifest/questions",
            params={"query": "GPU", "page_size": 5},
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["page"] == 1
        assert len(payload["items"]) <= 5
        assert payload["total"] > 0


def test_manifest_question_detail_is_candidate_safe() -> None:
    with TestClient(app) as client:
        response = client.get("/api/v1/manifest/questions/py-0001-bounded-cache")
        assert response.status_code == 200
        payload = response.json()
        assert payload["id"] == "PY-0001"
        assert payload["content_status"] == "planned"
        assert "interviewer_instructions" not in payload
        assert "reference_solution" not in payload

        missing = client.get("/api/v1/manifest/questions/does-not-exist")
        assert missing.status_code == 404


def test_structured_validation_error() -> None:
    with TestClient(app) as client:
        response = client.get("/api/v1/manifest/questions", params={"page_size": 1000})
        assert response.status_code == 422
        payload = response.json()
        assert payload["code"] == "request_validation_failed"
        assert payload["correlation_id"]
        assert payload["retryable"] is False
