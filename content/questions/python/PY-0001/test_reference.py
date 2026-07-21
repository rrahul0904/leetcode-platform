from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
from hypothesis import given
from hypothesis import strategies as st


def load_reference() -> ModuleType:
    path = Path(__file__).with_name("reference.py")
    spec = importlib.util.spec_from_file_location("py_0001_reference", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


reference = load_reference()
BoundedTTLCache: Any = reference.BoundedTTLCache


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def test_lru_eviction_respects_get_recency() -> None:
    clock = FakeClock()
    cache = BoundedTTLCache(2, clock)
    cache.set("a", 1, 10)
    cache.set("b", 2, 10)
    assert cache.get("a") == 1
    cache.set("c", 3, 10)
    with pytest.raises(KeyError):
        cache.get("b")
    assert cache.get("a") == 1
    assert cache.get("c") == 3


def test_exact_expiration_boundary_and_length_cleanup() -> None:
    clock = FakeClock()
    cache = BoundedTTLCache(2, clock)
    cache.set("short", 1, 5)
    cache.set("long", 2, 10)
    clock.now = 5
    with pytest.raises(KeyError):
        cache.get("short")
    assert len(cache) == 1


def test_expired_entry_does_not_evict_live_entry() -> None:
    clock = FakeClock()
    cache = BoundedTTLCache(2, clock)
    cache.set("expired", 1, 1)
    cache.set("live", 2, 20)
    clock.now = 2
    cache.set("new", 3, 20)
    assert cache.get("live") == 2
    assert cache.get("new") == 3


def test_validation_and_overwrite() -> None:
    clock = FakeClock()
    with pytest.raises(ValueError):
        BoundedTTLCache(0, clock)
    cache = BoundedTTLCache(1, clock)
    with pytest.raises(ValueError):
        cache.set("a", 1, 0)
    cache.set("a", 1, 2)
    clock.now = 1
    cache.set("a", 2, 5)
    clock.now = 3
    assert cache.get("a") == 2


@given(st.lists(st.integers(min_value=0, max_value=25), min_size=1, max_size=100))
def test_live_count_never_exceeds_capacity(keys: list[int]) -> None:
    clock = FakeClock()
    cache = BoundedTTLCache(5, clock)
    for key in keys:
        cache.set(key, key, ttl_seconds=10)
        assert len(cache) <= 5
