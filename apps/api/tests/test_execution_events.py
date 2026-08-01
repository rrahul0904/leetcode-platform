from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import pytest
from pydantic import ValidationError

from rigor_api.execution_events import (
    ExecutionCancelRequestedEvent,
    ExecutionRequestedEvent,
    parse_execution_queue_event,
)


def requested_payload() -> dict[str, object]:
    return {
        "schema_version": 1,
        "event_type": "execution.requested",
        "execution_id": "33333333-3333-3333-3333-333333333333",
        "attempt": 1,
        "requested_at": "2026-07-28T20:15:00+00:00",
        "trace_id": "trace-test",
    }


def test_requested_event_parses_strict_contract() -> None:
    event = parse_execution_queue_event(requested_payload())

    assert isinstance(event, ExecutionRequestedEvent)
    assert event.execution_id == UUID("33333333-3333-3333-3333-333333333333")
    assert event.requested_at == datetime(2026, 7, 28, 20, 15, tzinfo=UTC)


def test_cancel_event_parses_strict_contract() -> None:
    event = parse_execution_queue_event(
        {
            "schema_version": 1,
            "event_type": "execution.cancel_requested",
            "execution_id": "44444444-4444-4444-4444-444444444444",
            "requested_at": "2026-07-28T20:16:00+00:00",
            "trace_id": "trace-cancel",
        }
    )

    assert isinstance(event, ExecutionCancelRequestedEvent)


def test_unknown_or_future_event_version_fails_closed() -> None:
    payload = requested_payload()
    payload["schema_version"] = 2
    with pytest.raises(ValidationError):
        parse_execution_queue_event(payload)

    payload = requested_payload()
    payload["event_type"] = "execution.unknown"
    with pytest.raises(ValueError):
        parse_execution_queue_event(payload)


def test_queue_event_rejects_candidate_source_and_unknown_fields() -> None:
    payload = requested_payload()
    payload["source_code"] = "print('must not be queued')"

    with pytest.raises(ValidationError):
        parse_execution_queue_event(payload)
