from __future__ import annotations

from fastapi.routing import APIRoute

from rigor_api.main import app


def test_ai_arena_routes_are_registered() -> None:
    paths = {route.path for route in app.routes if isinstance(route, APIRoute)}
    assert "/api/v1/arena/challenges" in paths
    assert "/api/v1/arena/generate" in paths
    assert "/api/v1/arena/finalize" in paths
    assert "/api/v1/arena/me" in paths
    assert "/api/v1/arena/leaderboard" in paths
