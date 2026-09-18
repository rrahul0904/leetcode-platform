from __future__ import annotations

from fastapi.routing import APIRoute

from rigor_api.knowledge_company_readiness_routes import _completion_percent
from rigor_api.main import app


def test_completion_percent_handles_empty_and_partial_catalogs() -> None:
    assert _completion_percent(0, 0) == 0.0
    assert _completion_percent(1, 4) == 25.0
    assert _completion_percent(2, 3) == 66.7
    assert _completion_percent(3, 3) == 100.0


def test_company_readiness_route_is_registered() -> None:
    paths = {route.path for route in app.routes if isinstance(route, APIRoute)}
    assert "/api/v1/knowledge/me/company-readiness" in paths
