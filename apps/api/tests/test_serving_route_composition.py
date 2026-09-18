from __future__ import annotations

from fastapi.routing import APIRoute
from rigor_api import submissions as legacy_submissions
from rigor_api.main import app

EXPECTED_CANDIDATE_ROUTES = {
    ("POST", "/api/v1/questions/{slug}/run"): "queue_run_for_question",
    ("POST", "/api/v1/questions/{slug}/submissions"): "queue_submit_for_question",
    ("GET", "/api/v1/submissions"): "list_candidate_submissions",
    ("GET", "/api/v1/submissions/{submission_id}"): "get_candidate_submission",
    (
        "GET",
        "/api/v1/practice-sessions/{session_id}/submissions",
    ): "list_candidate_session_submissions",
    ("GET", "/api/v1/me/evidence"): "candidate_owned_evidence",
}
LEGACY_REPLACED_NAMES = {
    "run_question",
    "submit_question",
    "list_submissions",
    "get_submission",
    "list_session_submissions",
    "candidate_evidence",
}


def _endpoint_name(route: APIRoute) -> str:
    return str(getattr(route.endpoint, "__name__", ""))


def test_legacy_candidate_handlers_are_removed_before_serving() -> None:
    names = {
        _endpoint_name(route)
        for route in legacy_submissions.router.routes
        if isinstance(route, APIRoute)
    }

    assert names.isdisjoint(LEGACY_REPLACED_NAMES)


def test_serving_app_has_exactly_one_hardened_handler_for_each_candidate_path() -> None:
    routes = [route for route in app.routes if isinstance(route, APIRoute)]

    for (method, path), expected_endpoint in EXPECTED_CANDIDATE_ROUTES.items():
        matches = [
            route
            for route in routes
            if route.path == path and method in (route.methods or set())
        ]
        assert len(matches) == 1, (method, path, [_endpoint_name(route) for route in matches])
        assert _endpoint_name(matches[0]) == expected_endpoint
