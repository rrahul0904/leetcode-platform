from __future__ import annotations

from collections.abc import Mapping
from typing import TypedDict


class Job(TypedDict):
    rows: int
    depends_on: list[str]


def plan_backfill_batches(
    jobs: Mapping[str, Job], max_rows_per_batch: int
) -> list[list[str]]:
    if max_rows_per_batch <= 0:
        raise ValueError("max_rows_per_batch must be positive")
    normalized: dict[str, tuple[int, frozenset[str]]] = {}
    for job_id, job in jobs.items():
        if not job_id:
            raise ValueError("job IDs must be non-empty")
        rows = job["rows"]
        dependencies = frozenset(job["depends_on"])
        if rows <= 0 or rows > max_rows_per_batch:
            raise ValueError(f"invalid row estimate for {job_id}")
        if job_id in dependencies:
            raise ValueError(f"self-dependency for {job_id}")
        normalized[job_id] = (rows, dependencies)
    known = normalized.keys()
    for job_id, (_, dependencies) in normalized.items():
        missing = dependencies - known
        if missing:
            raise ValueError(f"missing dependencies for {job_id}: {sorted(missing)}")

    completed: set[str] = set()
    remaining = set(normalized)
    batches: list[list[str]] = []
    while remaining:
        ready = sorted(job_id for job_id in remaining if normalized[job_id][1] <= completed)
        if not ready:
            raise ValueError("dependency cycle detected")
        batch: list[str] = []
        rows_used = 0
        for job_id in ready:
            rows = normalized[job_id][0]
            if rows_used + rows <= max_rows_per_batch:
                batch.append(job_id)
                rows_used += rows
        if not batch:
            raise ValueError("no ready job fits the batch capacity")
        batches.append(batch)
        completed.update(batch)
        remaining.difference_update(batch)
    return batches
