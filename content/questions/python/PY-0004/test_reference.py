from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest


def load_reference() -> ModuleType:
    path = Path(__file__).with_name("reference.py")
    spec = importlib.util.spec_from_file_location("py_0004_reference", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


EvaluationWindowIndex: Any = load_reference().EvaluationWindowIndex


def test_unsorted_insertion_lookup_and_touching_windows() -> None:
    index = EvaluationWindowIndex()
    index.add(2, 3, "candidate")
    index.add(0, 1, "baseline")
    index.add(1, 2, "shadow")
    assert index.windows() == ((0.0, 1.0, "baseline"), (1.0, 2.0, "shadow"), (2.0, 3.0, "candidate"))
    assert index.find(0) == "baseline"
    assert index.find(1) == "shadow"
    assert index.find(3) is None


@pytest.mark.parametrize("start,end", [(0.5, 1.5), (-1, 0.1), (1.9, 4)])
def test_overlaps_are_rejected(start: float, end: float) -> None:
    index = EvaluationWindowIndex()
    index.add(0, 2, "existing")
    with pytest.raises(ValueError):
        index.add(start, end, "overlap")


def test_invalid_values_and_duplicate_labels_are_rejected() -> None:
    index = EvaluationWindowIndex()
    index.add(0, 1, "one")
    with pytest.raises(ValueError):
        index.add(2, 3, "one")
    with pytest.raises(ValueError):
        index.add(float("nan"), 3, "nan")
    with pytest.raises(ValueError):
        index.find(float("inf"))
