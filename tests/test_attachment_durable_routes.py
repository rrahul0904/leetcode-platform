from __future__ import annotations

from collections.abc import Iterator

from fastapi.routing import APIRoute

from rigor_api.main import app


def _walk_api_routes(root: object) -> Iterator[APIRoute]:
    """Traverse both flattened and nested FastAPI router representations."""

    stack: list[object] = [root]
    seen: set[int] = set()
    while stack:
        current = stack.pop()
        identity = id(current)
        if identity in seen:
            continue
        seen.add(identity)
        if isinstance(current, APIRoute):
            yield current
            continue
        routes = getattr(current, "routes", None)
        if isinstance(routes, (list, tuple)):
            stack.extend(routes)
        for attribute in ("original_router", "included_router"):
            nested = getattr(current, attribute, None)
            if nested is not None:
                stack.append(nested)


def _routes(path: str, method: str) -> list[APIRoute]:
    return [
        route
        for route in _walk_api_routes(app)
        if route.path == path and method in route.methods
    ]


def test_durable_run_route_replaces_legacy_synchronous_route() -> None:
    routes = _routes("/api/v1/questions/{slug}/run", "POST")
    assert len(routes) == 1
    assert routes[0].endpoint.__name__ == "queue_run_for_question"
    assert routes[0].status_code == 202


def test_durable_submit_route_replaces_legacy_synchronous_route() -> None:
    routes = _routes("/api/v1/questions/{slug}/submissions", "POST")
    assert len(routes) == 1
    assert routes[0].endpoint.__name__ == "queue_submit_for_question"
    assert routes[0].status_code == 202


def test_solution_reveal_route_is_registered_once() -> None:
    routes = _routes("/api/v1/questions/{slug}/solution", "GET")
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
        for route in _walk_api_routes(app)
        if route.path in candidate_paths
    }
    assert exposed.isdisjoint(forbidden)
