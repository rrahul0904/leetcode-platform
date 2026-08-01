from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from rigor_api.execution_dlq import DlqDisposition, DurableExecutionState, classify_event
from rigor_api.execution_domain import ExecutionStatus
from rigor_api.execution_events import ExecutionCancelRequestedEvent, ExecutionRequestedEvent

EXECUTION_ID = UUID("66666666-6666-6666-6666-666666666666")


def requested_event() -> ExecutionRequestedEvent:
    return ExecutionRequestedEvent(
        schema_version=1,
        event_type="execution.requested",
        execution_id=EXECUTION_ID,
        attempt=1,
        requested_at=datetime.now(UTC),
        trace_id="dlq-test",
    )


def cancel_event() -> ExecutionCancelRequestedEvent:
    return ExecutionCancelRequestedEvent(
        schema_version=1,
        event_type="execution.cancel_requested",
        execution_id=EXECUTION_ID,
        requested_at=datetime.now(UTC),
        trace_id="dlq-test",
    )


def state(status: ExecutionStatus, job: str | None = None) -> DurableExecutionState:
    return DurableExecutionState(status=status, kubernetes_job_name=job)


def test_requested_event_replays_only_while_execution_is_queued() -> None:
    event = requested_event()

    assert classify_event(event, state(ExecutionStatus.queued)) is DlqDisposition.replay
    assert (
        classify_event(event, state(ExecutionStatus.dispatching))
        is DlqDisposition.hold_in_progress
    )
    assert classify_event(event, state(ExecutionStatus.running)) is DlqDisposition.hold_in_progress
    assert (
        classify_event(event, state(ExecutionStatus.completed))
        is DlqDisposition.discard_terminal
    )
    assert classify_event(event, state(ExecutionStatus.failed)) is DlqDisposition.discard_terminal
    assert classify_event(event, state(ExecutionStatus.timeout)) is DlqDisposition.discard_terminal
    assert (
        classify_event(event, state(ExecutionStatus.cancelled))
        is DlqDisposition.discard_terminal
    )


def test_cancel_event_replays_only_when_cancelled_job_still_needs_cleanup() -> None:
    event = cancel_event()

    assert (
        classify_event(event, state(ExecutionStatus.cancelled, "execution-still-present"))
        is DlqDisposition.replay
    )
    assert (
        classify_event(event, state(ExecutionStatus.cancelled))
        is DlqDisposition.discard_terminal
    )
    assert classify_event(event, state(ExecutionStatus.running)) is DlqDisposition.hold_in_progress
    assert (
        classify_event(event, state(ExecutionStatus.completed))
        is DlqDisposition.discard_terminal
    )


def test_unknown_execution_is_held_for_operator_investigation() -> None:
    assert classify_event(requested_event(), None) is DlqDisposition.hold_unknown
