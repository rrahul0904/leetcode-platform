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


def test_durable_run_route_replaces_legacy_synchronous_route() -> None:
    routes = _post_routes("/api/v1/questions/{slug}/run")
    assert len(routes) == 1
    assert routes[0].endpoint.__name__ == "queue_run_for_question"
    assert routes[0].status_code == 202


def test_durable_submit_route_replaces_legacy_synchronous_route() -> None:
    routes = _post_routes("/api/v1/questions/{slug}/submissions")
    assert len(routes) == 1
    assert routes[0].endpoint.__name__ == "queue_submit_for_question"
    assert routes[0].status_code == 202


def test_solution_reveal_route_is_registered_once() -> None:
    routes = [
        route
        for route in app.routes
        if isinstance(route, APIRoute)
        and route.path == "/api/v1/questions/{slug}/solution"
        and "GET" in route.methods
    ]
    assert len(routes) == 1
    assert routes[0].endpoint.__name__ == "reveal_question_solution"


def test_candidate_execution_never_exposes_legacy_in_process_handlers() -> None:
    forbidden = {"run_question", "submit_question"}
    candidate_paths = {
        "/api/v1/questions/{slug}/run",
        "/api/v1/questions/{slug}/submissions",
    }
    exposed = {
        route.endpoint.__name__
        for route in app.routes
        if isinstance(route, APIRoute) and route.path in candidate_paths
    }
    assert exposed.isdisjoint(forbidden)
