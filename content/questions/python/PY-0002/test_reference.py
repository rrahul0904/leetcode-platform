from __future__ import annotations

import importlib.util
from copy import deepcopy
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest


def load_reference() -> ModuleType:
    path = Path(__file__).with_name("reference.py")
    spec = importlib.util.spec_from_file_location("py_0002_reference", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


plan_backfill_batches: Any = load_reference().plan_backfill_batches


def test_dependency_batches_and_capacity_are_deterministic() -> None:
    jobs = {
        "extract": {"rows": 4, "depends_on": []},
        "customers": {"rows": 3, "depends_on": ["extract"]},
        "orders": {"rows": 6, "depends_on": ["extract"]},
        "report": {"rows": 2, "depends_on": ["customers", "orders"]},
    }
    original = deepcopy(jobs)
    assert plan_backfill_batches(jobs, 7) == [
        ["extract"],
        ["customers"],
        ["orders"],
        ["report"],
    ]
    assert jobs == original


def test_independent_jobs_pack_in_lexicographic_order() -> None:
    jobs = {
        "c": {"rows": 2, "depends_on": []},
        "a": {"rows": 3, "depends_on": []},
        "b": {"rows": 2, "depends_on": []},
    }
    assert plan_backfill_batches(jobs, 5) == [["a", "b"], ["c"]]


@pytest.mark.parametrize(
    "jobs,capacity",
    [
        ({"a": {"rows": 1, "depends_on": ["missing"]}}, 2),
        ({"a": {"rows": 1, "depends_on": ["b"]}, "b": {"rows": 1, "depends_on": ["a"]}}, 2),
        ({"a": {"rows": 3, "depends_on": []}}, 2),
    ],
)
def test_invalid_graphs_are_rejected(jobs: dict[str, Any], capacity: int) -> None:
    with pytest.raises(ValueError):
        plan_backfill_batches(jobs, capacity)
