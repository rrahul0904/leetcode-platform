# ruff: noqa: I001\nfrom __future__ import annotations

from fastapi.routing import APIRoute

from rigor_api.ai_arena_routes import _challenge
from rigor_api.main import app


def test_ai_arena_routes_are_registered() -> None:
    paths = {route.path for route in app.routes if isinstance(route, APIRoute)}
    assert "/api/v1/arena/challenges" in paths
    assert "/api/v1/arena/generate" in paths
    assert "/api/v1/arena/finalize" in paths
    assert "/api/v1/arena/me" in paths
    assert "/api/v1/arena/leaderboard" in paths


def test_public_arena_challenge_never_serializes_hidden_test_bodies() -> None:
    challenge = _challenge(
        {
            "slug": "arena-security-contract",
            "title": "Arena Security Contract",
            "structured_content": {
                "question_type": "python_coding",
                "problem_statement": "Return the input value.",
                "public_constraints": ["Do not mutate the input."],
                "public_examples": [{"input": 1, "output": 1}],
                "mode_specification": {
                    "runtime": "python3.13",
                    "entrypoint": "solve",
                    "starter_code": "def solve(value):\n    pass\n",
                    "tests": [
                        {
                            "id": "public-1",
                            "visibility": "public",
                            "input": {"value": 1},
                            "expected": 1,
                        },
                        {
                            "id": "hidden-1",
                            "visibility": "hidden",
                            "input": {"value": 999},
                            "expected": 999,
                        },
                    ],
                },
            },
        }
    )

    payload = challenge.model_dump(mode="json")
    assert payload["public_test_count"] == 1
    assert payload["hidden_test_count"] == 1
    assert "tests" not in payload
    assert "hidden_tests" not in payload
    assert "999" not in str(payload)
