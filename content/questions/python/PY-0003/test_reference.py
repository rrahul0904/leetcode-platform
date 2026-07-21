from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest


def load_reference() -> ModuleType:
    path = Path(__file__).with_name("reference.py")
    spec = importlib.util.spec_from_file_location("py_0003_reference", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


EventTimeCounter: Any = load_reference().EventTimeCounter


def test_out_of_order_watermark_and_window_boundaries() -> None:
    counter = EventTimeCounter(5)
    assert counter.record("latest", 10, 3)
    assert counter.record("boundary", 5, 2)
    with pytest.raises(ValueError):
        counter.record("late", 4.999, 9)
    assert counter.sum_between(5, 10) == 2
    assert counter.sum_between(5, 10.001) == 5


def test_exact_retry_is_idempotent_after_watermark_moves() -> None:
    counter = EventTimeCounter(1)
    assert counter.record("old", 1, 4)
    assert counter.record("new", 100, 2)
    assert counter.record("old", 1, 4) is False
    with pytest.raises(ValueError):
        counter.record("old", 1, 5)


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_non_finite_values_are_rejected(value: float) -> None:
    counter = EventTimeCounter(1)
    with pytest.raises(ValueError):
        counter.record("event", value, 1)


def test_invalid_constructor_and_query_are_rejected() -> None:
    with pytest.raises(ValueError):
        EventTimeCounter(-1)
    counter = EventTimeCounter(0)
    with pytest.raises(ValueError):
        counter.sum_between(2, 2)
