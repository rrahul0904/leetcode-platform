from __future__ import annotations

from fastapi.routing import APIRoute

from rigor_api.main import app


def _post_routes(path: str) -> list[APIRoute]:
    return [
        route
        for route in app.routes
        if isinstance(route, APIRoute)
        and route.path == path
        and "POST" in route.methods
    ]


def test_durable_run_route_precedes_legacy_synchronous_route() -> None:
    routes = _post_routes("/api/v1/questions/{slug}/run")
    assert routes
    assert routes[0].endpoint.__name__ == "queue_run_for_question"
    assert routes[0].status_code == 202


def test_durable_submit_route_precedes_legacy_synchronous_route() -> None:
    routes = _post_routes("/api/v1/questions/{slug}/submissions")
    assert routes
    assert routes[0].endpoint.__name__ == "queue_submit_for_question"
    assert routes[0].status_code == 202


def test_solution_reveal_route_is_registered() -> None:
    paths = {
        route.path
        for route in app.routes
        if isinstance(route, APIRoute) and "GET" in route.methods
    }
    assert "/api/v1/questions/{slug}/solution" in paths
