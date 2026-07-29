from __future__ import annotations

from fastapi.routing import APIRoute

from rigor_api.main import app


def _post_routes(path: str) -> list[APIRoute]:
    return [
        route
        for route in app.routes
        if isinstance(route, APIRoute) and route.path == path and "POST" in route.methods
    ]


def test_public_run_route_is_async_handler() -> None:
    routes = _post_routes("/api/v1/questions/{slug}/run")

    assert routes
    assert routes[0].endpoint.__name__ == "queue_run_for_question"
    assert routes[0].status_code == 202


def test_public_submit_route_is_async_handler() -> None:
    routes = _post_routes("/api/v1/questions/{slug}/submissions")

    assert routes
    assert routes[0].endpoint.__name__ == "queue_submit_for_question"
    assert routes[0].status_code == 202


def test_execution_status_and_cancel_routes_are_registered() -> None:
    registered = {
        (route.path, method)
        for route in app.routes
        if isinstance(route, APIRoute)
        for method in route.methods
    }

    assert ("/api/v1/executions/{execution_id}", "GET") in registered
    assert ("/api/v1/executions/{execution_id}/cancel", "POST") in registered
    assert ("/api/v1/executions/run", "POST") not in registered
    assert ("/api/v1/executions/submit", "POST") not in registered
