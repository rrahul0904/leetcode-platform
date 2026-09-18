from __future__ import annotations

from fastapi.routing import APIRoute

from rigor_api.main import app


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
