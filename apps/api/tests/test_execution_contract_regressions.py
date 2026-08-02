from __future__ import annotations

import pytest
from fastapi import HTTPException

from rigor_api.execution_api import _entrypoint, _invocation_mode


def _question(mode: dict[str, object]) -> dict[str, object]:
    return {"structured_content": {"mode_specification": mode}}


def test_legacy_starter_function_defines_entrypoint() -> None:
    question = _question(
        {
            "runtime": "3.13",
            "starter_code": "def allocate_resource_windows(requests, capacity):\n    ...\n",
        }
    )

    assert _entrypoint(question) == "allocate_resource_windows"


def test_explicit_entrypoint_wins_over_starter_parsing() -> None:
    question = _question(
        {
            "entrypoint": "evaluate_candidate",
            "starter_code": "def helper():\n    ...\n\ndef evaluate_candidate(value):\n    ...\n",
        }
    )

    assert _entrypoint(question) == "evaluate_candidate"


def test_ambiguous_legacy_starter_fails_closed() -> None:
    question = _question(
        {
            "starter_code": "def first(value):\n    ...\n\ndef second(value):\n    ...\n",
        }
    )

    with pytest.raises(HTTPException, match="unambiguous"):
        _entrypoint(question)


def test_invocation_mode_defaults_to_auto_and_rejects_unknown_values() -> None:
    question = _question({"starter_code": "def solve(value): return value"})
    assert _invocation_mode(question) == "auto"

    with pytest.raises(HTTPException, match="invocation mode"):
        _invocation_mode(_question({"invocation_mode": "magic"}))
