from __future__ import annotations

import math


class EventTimeCounter:
    def __init__(self, allowed_lateness: float) -> None:
        if not isinstance(allowed_lateness, (int, float)) or not math.isfinite(allowed_lateness):
            raise ValueError("allowed_lateness must be finite")
        if allowed_lateness < 0:
            raise ValueError("allowed_lateness must be non-negative")
        self._allowed_lateness = float(allowed_lateness)
        self._max_timestamp: float | None = None
        self._by_id: dict[str, tuple[float, float]] = {}
        self._events: list[tuple[float, float]] = []

    @staticmethod
    def _finite_number(value: float, name: str) -> float:
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise ValueError(f"{name} must be numeric")
        converted = float(value)
        if not math.isfinite(converted):
            raise ValueError(f"{name} must be finite")
        return converted

    def record(self, event_id: str, timestamp: float, value: float) -> bool:
        if not event_id:
            raise ValueError("event_id must be non-empty")
        event_time = self._finite_number(timestamp, "timestamp")
        event_value = self._finite_number(value, "value")
        payload = (event_time, event_value)
        previous = self._by_id.get(event_id)
        if previous is not None:
            if previous == payload:
                return False
            raise ValueError("event ID was reused with a different payload")
        if self._max_timestamp is not None:
            watermark = self._max_timestamp - self._allowed_lateness
            if event_time < watermark:
                raise ValueError("event is older than the watermark")
        self._by_id[event_id] = payload
        self._events.append(payload)
        self._max_timestamp = (
            event_time if self._max_timestamp is None else max(self._max_timestamp, event_time)
        )
        return True

    def sum_between(self, start: float, end: float) -> float:
        window_start = self._finite_number(start, "start")
        window_end = self._finite_number(end, "end")
        if window_start >= window_end:
            raise ValueError("start must be less than end")
        return sum(value for timestamp, value in self._events if window_start <= timestamp < window_end)
