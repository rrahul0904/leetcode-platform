from __future__ import annotations

import argparse
import json
import logging
import os
from dataclasses import dataclass
from enum import StrEnum
from typing import cast

from sqlalchemy import Engine, create_engine, text

from .execution_domain import ExecutionStatus
from .execution_events import (
    ExecutionCancelRequestedEvent,
    ExecutionQueueEvent,
    ExecutionRequestedEvent,
    parse_execution_queue_event,
)
from .execution_sqs import SqsJsonClient, SqsReceivedMessage

logger = logging.getLogger("rigor.execution-dlq")


class DlqDisposition(StrEnum):
    replay = "REPLAY"
    discard_terminal = "DISCARD_TERMINAL"
    hold_in_progress = "HOLD_IN_PROGRESS"
    hold_unknown = "HOLD_UNKNOWN"
    hold_malformed = "HOLD_MALFORMED"


@dataclass(frozen=True)
class DurableExecutionState:
    status: ExecutionStatus
    kubernetes_job_name: str | None


@dataclass(frozen=True)
class DlqClassification:
    message_id: str
    execution_id: str | None
    event_type: str | None
    disposition: DlqDisposition
    reason: str


def classify_event(
    event: ExecutionQueueEvent,
    state: DurableExecutionState | None,
) -> DlqDisposition:
    if state is None:
        return DlqDisposition.hold_unknown

    if isinstance(event, ExecutionRequestedEvent):
        if state.status is ExecutionStatus.queued:
            return DlqDisposition.replay
        if state.status in {ExecutionStatus.dispatching, ExecutionStatus.running}:
            return DlqDisposition.hold_in_progress
        return DlqDisposition.discard_terminal

    if isinstance(event, ExecutionCancelRequestedEvent):
        if state.status is ExecutionStatus.cancelled and state.kubernetes_job_name:
            return DlqDisposition.replay
        if state.status is ExecutionStatus.cancelled:
            return DlqDisposition.discard_terminal
        if state.status in {ExecutionStatus.queued, ExecutionStatus.dispatching, ExecutionStatus.running}:
            return DlqDisposition.hold_in_progress
        return DlqDisposition.discard_terminal

    return DlqDisposition.hold_malformed


def _load_state(engine: Engine, event: ExecutionQueueEvent) -> DurableExecutionState | None:
    with engine.connect() as connection:
        row = (
            connection.execute(
                text(
                    """
                    SELECT state::text AS state, kubernetes_job_name
                    FROM execution_requests
                    WHERE id=:execution_id
                    """
                ),
                {"execution_id": event.execution_id},
            )
            .mappings()
            .one_or_none()
        )
    if row is None:
        return None
    return DurableExecutionState(
        status=ExecutionStatus(str(row["state"])),
        kubernetes_job_name=(
            str(row["kubernetes_job_name"]) if row["kubernetes_job_name"] else None
        ),
    )


def classify_message(engine: Engine, message: SqsReceivedMessage) -> DlqClassification:
    try:
        decoded: object = json.loads(message.body)
        event = parse_execution_queue_event(decoded)
    except (ValueError, json.JSONDecodeError) as exc:
        return DlqClassification(
            message_id=message.message_id,
            execution_id=None,
            event_type=None,
            disposition=DlqDisposition.hold_malformed,
            reason=f"malformed:{exc.__class__.__name__}",
        )

    state = _load_state(engine, event)
    disposition = classify_event(event, state)
    return DlqClassification(
        message_id=message.message_id,
        execution_id=str(event.execution_id),
        event_type=event.event_type,
        disposition=disposition,
        reason=(
            f"database_state={state.status.value}"
            if state is not None
            else "execution_not_found"
        ),
    )


def _clients() -> tuple[Engine, SqsJsonClient, SqsJsonClient]:
    database_url = os.getenv("RIGOR_EXECUTOR_DATABASE_URL", "")
    queue_url = os.getenv("RIGOR_EXECUTION_QUEUE_URL", "")
    dlq_url = os.getenv("RIGOR_EXECUTION_DLQ_URL", "")
    region = os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION") or ""
    if not database_url:
        raise RuntimeError("RIGOR_EXECUTOR_DATABASE_URL is required.")
    if not queue_url:
        raise RuntimeError("RIGOR_EXECUTION_QUEUE_URL is required.")
    if not dlq_url:
        raise RuntimeError("RIGOR_EXECUTION_DLQ_URL is required.")
    if not region:
        raise RuntimeError("AWS_REGION is required.")
    return (
        create_engine(database_url, pool_pre_ping=True),
        SqsJsonClient(queue_url=queue_url, region=region),
        SqsJsonClient(queue_url=dlq_url, region=region),
    )


def _print_classification(classification: DlqClassification) -> None:
    print(
        json.dumps(
            {
                "message_id": classification.message_id,
                "execution_id": classification.execution_id,
                "event_type": classification.event_type,
                "disposition": classification.disposition.value,
                "reason": classification.reason,
            },
            separators=(",", ":"),
        )
    )


def inspect_batch(engine: Engine, dlq: SqsJsonClient, *, limit: int) -> int:
    messages = dlq.receive_messages(maximum=limit, wait_seconds=0, visibility_timeout=15)
    for message in messages:
        _print_classification(classify_message(engine, message))
        dlq.change_message_visibility(message.receipt_handle, 0)
    return len(messages)


def replay_batch(
    engine: Engine,
    queue: SqsJsonClient,
    dlq: SqsJsonClient,
    *,
    limit: int,
) -> int:
    replayed = 0
    messages = dlq.receive_messages(maximum=limit, wait_seconds=0, visibility_timeout=30)
    for message in messages:
        classification = classify_message(engine, message)
        _print_classification(classification)
        if classification.disposition is DlqDisposition.replay:
            queue.send_message(message.body)
            dlq.delete_message(message.receipt_handle)
            replayed += 1
        else:
            dlq.change_message_visibility(message.receipt_handle, 0)
    return replayed


def discard_terminal_batch(engine: Engine, dlq: SqsJsonClient, *, limit: int) -> int:
    discarded = 0
    messages = dlq.receive_messages(maximum=limit, wait_seconds=0, visibility_timeout=30)
    for message in messages:
        classification = classify_message(engine, message)
        _print_classification(classification)
        if classification.disposition is DlqDisposition.discard_terminal:
            dlq.delete_message(message.receipt_handle)
            discarded += 1
        else:
            dlq.change_message_visibility(message.receipt_handle, 0)
    return discarded


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Rigor execution DLQ operator")
    parser.add_argument("action", choices=("inspect", "replay", "discard-terminal"))
    parser.add_argument("--limit", type=int, default=10)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    limit = cast(int, args.limit)
    if not 1 <= limit <= 10:
        raise SystemExit("--limit must be between 1 and 10")
    engine, queue, dlq = _clients()
    try:
        if args.action == "inspect":
            count = inspect_batch(engine, dlq, limit=limit)
            logger.info("execution.dlq_inspected", extra={"count": count})
            return 0
        if args.action == "replay":
            count = replay_batch(engine, queue, dlq, limit=limit)
            logger.info("execution.dlq_replayed", extra={"count": count})
            return 0
        count = discard_terminal_batch(engine, dlq, limit=limit)
        logger.info("execution.dlq_terminal_discarded", extra={"count": count})
        return 0
    finally:
        engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
