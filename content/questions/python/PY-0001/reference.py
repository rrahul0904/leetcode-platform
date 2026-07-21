from __future__ import annotations

from collections import OrderedDict
from collections.abc import Callable, Hashable
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class _Entry[V]:
    value: V
    expires_at: float


class BoundedTTLCache[K: Hashable, V]:
    def __init__(self, capacity: int, clock: Callable[[], float]) -> None:
        if capacity <= 0:
            raise ValueError("capacity must be positive")
        self._capacity = capacity
        self._clock = clock
        self._entries: OrderedDict[K, _Entry[V]] = OrderedDict()

    def _purge_expired(self, now: float) -> None:
        expired = [key for key, entry in self._entries.items() if now >= entry.expires_at]
        for key in expired:
            del self._entries[key]

    def get(self, key: K) -> V:
        entry = self._entries.get(key)
        if entry is None:
            raise KeyError(key)
        if self._clock() >= entry.expires_at:
            del self._entries[key]
            raise KeyError(key)
        self._entries.move_to_end(key)
        return entry.value

    def set(self, key: K, value: V, ttl_seconds: float) -> None:
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be positive")
        now = self._clock()
        self._purge_expired(now)
        self._entries[key] = _Entry(value=value, expires_at=now + ttl_seconds)
        self._entries.move_to_end(key)
        while len(self._entries) > self._capacity:
            self._entries.popitem(last=False)

    def __len__(self) -> int:
        self._purge_expired(self._clock())
        return len(self._entries)
