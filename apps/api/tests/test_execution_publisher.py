from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from rigor_api.execution_publisher import publish_claimed_messages
from rigor_api.outbox import OutboxMessage


class FakeOutbox:
    def __init__(self, messages: list[OutboxMessage]) -> None:
        self.messages = messages
        self.published: list[UUID] = []
        self.failed: list[tuple[UUID, int, str]] = []

    def claim_batch(self, *, limit: int = 25) -> list[OutboxMessage]:
        return self.messages[:limit]

    def mark_published(self, message_id: UUID) -> None:
        self.published.append(message_id)

    def mark_failed(
        self,
        message_id: UUID,
        *,
        attempt_count: int,
        error: str,
        jitter_ratio: float | None = None,
    ) -> datetime:
        del jitter_ratio
        self.failed.append((message_id, attempt_count, error))
        return datetime(2026, 7, 28, tzinfo=UTC)


class FakePublisher:
    def __init__(self, *, fail_ids: set[UUID] | None = None) -> None:
        self.fail_ids = fail_ids or set()
        self.sent: list[UUID] = []

    def publish(self, message: OutboxMessage) -> None:
        self.sent.append(message.id)
        if message.id in self.fail_ids:
            raise TimeoutError("simulated queue timeout")


def message(value: int, *, attempts: int = 0) -> OutboxMessage:
    message_id = UUID(int=value)
    return OutboxMessage(
        id=message_id,
        aggregate_type="execution",
        aggregate_id=UUID(int=100 + value),
        event_type="execution.requested",
        payload={"execution_id": str(UUID(int=100 + value))},
        created_at=datetime(2026, 7, 28, tzinfo=UTC),
        attempt_count=attempts,
    )


def test_publish_claimed_messages_marks_successes_published() -> None:
    messages = [message(1), message(2)]
    outbox = FakeOutbox(messages)
    publisher = FakePublisher()

    result = publish_claimed_messages(outbox, publisher)

    assert result.claimed == 2
    assert result.published == 2
    assert result.failed == 0
    assert outbox.published == [messages[0].id, messages[1].id]
    assert outbox.failed == []


def test_publish_claimed_messages_records_failure_without_losing_other_messages() -> None:
    first = message(1, attempts=2)
    second = message(2)
    outbox = FakeOutbox([first, second])
    publisher = FakePublisher(fail_ids={first.id})

    result = publish_claimed_messages(outbox, publisher)

    assert result.claimed == 2
    assert result.published == 1
    assert result.failed == 1
    assert outbox.failed == [(first.id, 2, "TimeoutError")]
    assert outbox.published == [second.id]
