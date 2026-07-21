from __future__ import annotations

import math
from bisect import bisect_left, bisect_right
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class _Window:
    start: float
    end: float
    label: str


class EvaluationWindowIndex:
    def __init__(self) -> None:
        self._starts: list[float] = []
        self._windows: list[_Window] = []
        self._labels: set[str] = set()

    @staticmethod
    def _finite(value: float, name: str) -> float:
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise ValueError(f"{name} must be numeric")
        converted = float(value)
        if not math.isfinite(converted):
            raise ValueError(f"{name} must be finite")
        return converted

    def add(self, start: float, end: float, label: str) -> None:
        window_start = self._finite(start, "start")
        window_end = self._finite(end, "end")
        if window_start >= window_end:
            raise ValueError("start must be less than end")
        if not label or label in self._labels:
            raise ValueError("label must be non-empty and unique")
        position = bisect_left(self._starts, window_start)
        if position > 0 and self._windows[position - 1].end > window_start:
            raise ValueError("window overlaps its predecessor")
        if position < len(self._windows) and self._windows[position].start < window_end:
            raise ValueError("window overlaps its successor")
        self._starts.insert(position, window_start)
        self._windows.insert(position, _Window(window_start, window_end, label))
        self._labels.add(label)

    def find(self, timestamp: float) -> str | None:
        point = self._finite(timestamp, "timestamp")
        position = bisect_right(self._starts, point) - 1
        if position < 0:
            return None
        window = self._windows[position]
        return window.label if point < window.end else None

    def windows(self) -> tuple[tuple[float, float, str], ...]:
        return tuple((window.start, window.end, window.label) for window in self._windows)
