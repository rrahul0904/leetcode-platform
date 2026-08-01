from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import Connection, text


@dataclass(frozen=True)
class OutboxMessage:
    id: UUID
    aggregate_type: str
    aggregate_id: UUID
    event_type: str
    payload: dict[str, object]
    created_at: datetime
    attempt_count: int


def retry_delay_seconds(
    attempt_count: int,
    *,
    base_seconds: float = 1.0,
    cap_seconds: float = 300.0,
    jitter_ratio: float,
) -> float:
    """Return capped exponential backoff with bounded positive jitter."""
    if attempt_count < 0:
        raise ValueError("attempt_count must be non-negative")
    if not 0.0 <= jitter_ratio <= 1.0:
        raise ValueError("jitter_ratio must be between 0 and 1")
    exponential = min(cap_seconds, base_seconds * (2**attempt_count))
    return min(cap_seconds, exponential * (0.5 + 0.5 * jitter_ratio))


class ExecutionOutboxRepository:
    def __init__(self, connection: Connection) -> None:
        self._connection = connection

    def claim_batch(self, *, limit: int = 25) -> list[OutboxMessage]:
        if not 1 <= limit <= 100:
            raise ValueError("limit must be between 1 and 100")
        rows = (
            self._connection.execute(
                text(
                    """
                    SELECT
                        id,
                        aggregate_type,
                        aggregate_id,
                        event_type,
                        payload,
                        created_at,
                        attempt_count
                    FROM execution_outbox
                    WHERE published_at IS NULL
                      AND next_attempt_at <= CURRENT_TIMESTAMP
                    ORDER BY created_at, id
                    FOR UPDATE SKIP LOCKED
                    LIMIT :limit
                    """
                ),
                {"limit": limit},
            )
            .mappings()
            .all()
        )
        return [
            OutboxMessage(
                id=UUID(str(row["id"])),
                aggregate_type=str(row["aggregate_type"]),
                aggregate_id=UUID(str(row["aggregate_id"])),
                event_type=str(row["event_type"]),
                payload=dict(row["payload"]) if isinstance(row["payload"], dict) else {},
                created_at=row["created_at"],
                attempt_count=int(row["attempt_count"]),
            )
            for row in rows
        ]

    def mark_published(self, message_id: UUID) -> None:
        self._connection.execute(
            text(
                """
                UPDATE execution_outbox
                SET published_at=CURRENT_TIMESTAMP,
                    last_error=NULL
                WHERE id=:message_id
                  AND published_at IS NULL
                """
            ),
            {"message_id": message_id},
        )

    def mark_failed(
        self,
        message_id: UUID,
        *,
        attempt_count: int,
        error: str,
        jitter_ratio: float | None = None,
    ) -> datetime:
        selected_jitter = random.random() if jitter_ratio is None else jitter_ratio
        delay = retry_delay_seconds(
            attempt_count,
            jitter_ratio=selected_jitter,
        )
        next_attempt_at = datetime.now(UTC) + timedelta(seconds=delay)
        self._connection.execute(
            text(
                """
                UPDATE execution_outbox
                SET attempt_count=attempt_count + 1,
                    next_attempt_at=:next_attempt_at,
                    last_error=:last_error
                WHERE id=:message_id
                  AND published_at IS NULL
                """
            ),
            {
                "message_id": message_id,
                "next_attempt_at": next_attempt_at,
                "last_error": error[:4000],
            },
        )
        return next_attempt_at
