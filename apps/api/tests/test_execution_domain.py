from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import pytest

from rigor_api.execution_domain import (
    LEGAL_EXECUTION_TRANSITIONS,
    TERMINAL_EXECUTION_STATUSES,
    ExecutionStatus,
    ExecutionTransitionError,
    ExecutionType,
    execution_request_hash,
    execution_requested_event,
    normalize_execution_status,
    validate_execution_transition,
)


@pytest.mark.parametrize(
    ("current", "target"),
    [
        (ExecutionStatus.queued, ExecutionStatus.dispatching),
        (ExecutionStatus.queued, ExecutionStatus.cancelled),
        (ExecutionStatus.dispatching, ExecutionStatus.running),
        (ExecutionStatus.dispatching, ExecutionStatus.failed),
        (ExecutionStatus.dispatching, ExecutionStatus.cancelled),
        (ExecutionStatus.running, ExecutionStatus.completed),
        (ExecutionStatus.running, ExecutionStatus.failed),
        (ExecutionStatus.running, ExecutionStatus.timeout),
        (ExecutionStatus.running, ExecutionStatus.cancelled),
    ],
)
def test_legal_execution_transitions(
    current: ExecutionStatus,
    target: ExecutionStatus,
) -> None:
    validate_execution_transition(current, target)
    assert target in LEGAL_EXECUTION_TRANSITIONS[current]


@pytest.mark.parametrize(
    ("current", "target"),
    [
        (ExecutionStatus.queued, ExecutionStatus.running),
        (ExecutionStatus.completed, ExecutionStatus.running),
        (ExecutionStatus.failed, ExecutionStatus.completed),
        (ExecutionStatus.timeout, ExecutionStatus.running),
        (ExecutionStatus.cancelled, ExecutionStatus.running),
        (ExecutionStatus.completed, ExecutionStatus.cancelled),
    ],
)
def test_illegal_execution_transitions_fail(
    current: ExecutionStatus,
    target: ExecutionStatus,
) -> None:
    with pytest.raises(ExecutionTransitionError):
        validate_execution_transition(current, target)


def test_terminal_states_have_no_outgoing_transitions() -> None:
    assert TERMINAL_EXECUTION_STATUSES == {
        ExecutionStatus.completed,
        ExecutionStatus.failed,
        ExecutionStatus.timeout,
        ExecutionStatus.cancelled,
    }
    for state in TERMINAL_EXECUTION_STATUSES:
        assert LEGAL_EXECUTION_TRANSITIONS[state] == frozenset()


def test_execution_request_hash_is_deterministic_and_request_specific() -> None:
    session_id = UUID("11111111-1111-1111-1111-111111111111")
    question_version_id = UUID("22222222-2222-2222-2222-222222222222")
    common = {
        "execution_type": ExecutionType.run,
        "practice_session_id": session_id,
        "question_version_id": question_version_id,
        "runtime": "python3.13",
        "source_code": "def solve(value):\n    return value + 1\n",
    }

    first = execution_request_hash(**common)
    second = execution_request_hash(**common)
    changed = execution_request_hash(
        **{
            **common,
            "source_code": "def solve(value):\n    return value + 2\n",
        }
    )

    assert first == second
    assert first != changed
    assert len(first) == 64


def test_legacy_execution_statuses_normalize_without_expanding_public_state_machine() -> None:
    assert normalize_execution_status("PASSED") == ExecutionStatus.completed
    assert normalize_execution_status("ERROR") == ExecutionStatus.failed
    assert normalize_execution_status("TIMED_OUT") == ExecutionStatus.timeout
    assert normalize_execution_status("QUEUED") == ExecutionStatus.queued


def test_execution_requested_event_is_versioned_and_source_free() -> None:
    execution_id = UUID("33333333-3333-3333-3333-333333333333")
    requested_at = datetime(2026, 7, 28, 20, 15, tzinfo=UTC)

    event = execution_requested_event(
        execution_id=execution_id,
        requested_at=requested_at,
        trace_id="trace-test",
    )

    assert event == {
        "schema_version": 1,
        "event_type": "execution.requested",
        "execution_id": str(execution_id),
        "attempt": 1,
        "requested_at": requested_at.isoformat(),
        "trace_id": "trace-test",
    }
    assert "source_code" not in event
    assert "input_payload" not in event
