from __future__ import annotations

from fastapi.routing import APIRoute

from rigor_api.main import app


def _post_routes(path: str) -> list[APIRoute]:
    return [
        route
        for route in app.routes
        if isinstance(route, APIRoute) and route.path == path and "POST" in route.methods
    ]


def test_legacy_run_route_is_shadowed_by_fail_closed_handler() -> None:
    routes = _post_routes("/api/v1/questions/{slug}/run")

    assert routes
    assert routes[0].endpoint.__name__ == "legacy_synchronous_run_disabled"


def test_legacy_submit_route_is_shadowed_by_fail_closed_handler() -> None:
    routes = _post_routes("/api/v1/questions/{slug}/submissions")

    assert routes
    assert routes[0].endpoint.__name__ == "legacy_synchronous_submit_disabled"


def test_async_execution_routes_are_registered() -> None:
    registered = {
        (route.path, method)
        for route in app.routes
        if isinstance(route, APIRoute)
        for method in route.methods
    }

    assert ("/api/v1/executions/run", "POST") in registered
    assert ("/api/v1/executions/submit", "POST") in registered
    assert ("/api/v1/executions/{execution_id}", "GET") in registered
    assert ("/api/v1/executions/{execution_id}/cancel", "POST") in registered
