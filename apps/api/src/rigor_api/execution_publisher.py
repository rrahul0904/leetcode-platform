from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from sqlalchemy import Connection

from .outbox import ExecutionOutboxRepository, OutboxMessage


class ExecutionQueuePublisher(Protocol):
    """Port implemented by the production SQS adapter.

    Implementations may deliver more than once. Downstream execution claiming is
    therefore required to remain idempotent even when this call succeeds and the
    subsequent database commit does not.
    """

    def publish(self, message: OutboxMessage) -> None: ...


class ExecutionOutboxStore(Protocol):
    def claim_batch(self, *, limit: int = 25) -> list[OutboxMessage]: ...

    def mark_published(self, message_id: UUID) -> None: ...

    def mark_failed(
        self,
        message_id: UUID,
        *,
        attempt_count: int,
        error: str,
        jitter_ratio: float | None = None,
    ) -> datetime: ...


@dataclass(frozen=True)
class PublishBatchResult:
    claimed: int
    published: int
    failed: int


def publish_claimed_messages(
    outbox: ExecutionOutboxStore,
    publisher: ExecutionQueuePublisher,
    *,
    limit: int = 25,
) -> PublishBatchResult:
    messages = outbox.claim_batch(limit=limit)
    published = 0
    failed = 0

    for message in messages:
        try:
            publisher.publish(message)
        except Exception as exc:  # transport boundary; retry is intentionally durable
            failed += 1
            outbox.mark_failed(
                message.id,
                attempt_count=message.attempt_count,
                error=exc.__class__.__name__,
            )
        else:
            published += 1
            outbox.mark_published(message.id)

    return PublishBatchResult(
        claimed=len(messages),
        published=published,
        failed=failed,
    )


def publish_outbox_batch(
    connection: Connection,
    publisher: ExecutionQueuePublisher,
    *,
    limit: int = 25,
) -> PublishBatchResult:
    """Publish one locked batch inside the caller's database transaction.

    If queue delivery succeeds but the transaction later rolls back, the row is
    retried and the queue may receive a duplicate. This is expected and is why the
    dispatcher must atomically claim executions rather than assuming exactly-once
    queue delivery.
    """

    return publish_claimed_messages(
        ExecutionOutboxRepository(connection),
        publisher,
        limit=limit,
    )
