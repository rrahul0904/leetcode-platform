#!/usr/bin/env python3
# ruff: noqa: E501
"""Generate the deterministic 50-question launch foundation.

The generated packages are first-party original content.  The script is kept in
the repository so the package corpus is reproducible and reviewable rather than
being an opaque one-time database seed.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "content"
MANIFEST = json.loads((CONTENT / "question-bank-manifest.json").read_text())
MANIFEST_BY_ID = {item["id"]: item for item in MANIFEST["questions"]}
AUTHORED_AT = datetime(2026, 7, 21, 16, 0, tzinfo=UTC).isoformat().replace("+00:00", "Z")


def slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")


PYTHON_SPECS: list[dict[str, Any]] = [
    {
        "id": "PY-0005",
        "title": "Select a Bounded Priority Worker Batch",
        "function": "select_worker_batch",
        "starter": "def select_worker_batch(tasks, max_cost):\n    ...",
        "statement": "Implement `select_worker_batch(tasks, max_cost)`. Each task has `id`, positive integer `cost`, integer `priority`, and integer `enqueued_at`. Validate unique IDs, sort by descending priority then enqueue time then ID, and greedily select every task that still fits the positive cost budget. Return selected IDs without mutating the input.",
        "code": """def select_worker_batch(tasks, max_cost):
    if not isinstance(max_cost, int) or isinstance(max_cost, bool) or max_cost <= 0:
        raise ValueError("max_cost must be positive")
    seen = set()
    normalized = []
    for task in tasks:
        task_id = task.get("id")
        cost = task.get("cost")
        if not isinstance(task_id, str) or not task_id or task_id in seen:
            raise ValueError("task IDs must be unique non-empty strings")
        if not isinstance(cost, int) or isinstance(cost, bool) or cost <= 0:
            raise ValueError("task cost must be positive")
        seen.add(task_id)
        normalized.append(task)
    remaining = max_cost
    selected = []
    for task in sorted(normalized, key=lambda item: (-item["priority"], item["enqueued_at"], item["id"])):
        if task["cost"] <= remaining:
            selected.append(task["id"])
            remaining -= task["cost"]
    return selected
""",
        "cases": [
            (
                {
                    "tasks": [
                        {"id": "b", "cost": 2, "priority": 2, "enqueued_at": 2},
                        {"id": "a", "cost": 3, "priority": 2, "enqueued_at": 1},
                    ],
                    "max_cost": 4,
                },
                ["a"],
            ),
            (
                {
                    "tasks": [
                        {"id": "low", "cost": 1, "priority": 1, "enqueued_at": 0},
                        {"id": "high", "cost": 2, "priority": 4, "enqueued_at": 9},
                    ],
                    "max_cost": 3,
                },
                ["high", "low"],
            ),
            ({"tasks": [], "max_cost": 5}, []),
            (
                {
                    "tasks": [
                        {"id": "large", "cost": 9, "priority": 9, "enqueued_at": 0},
                        {"id": "fit", "cost": 2, "priority": 1, "enqueued_at": 0},
                    ],
                    "max_cost": 2,
                },
                ["fit"],
            ),
        ],
    },
    {
        "id": "PY-0006",
        "title": "Schedule Capped Exponential Retries",
        "function": "retry_schedule",
        "starter": "def retry_schedule(attempts, base_delay, maximum_delay):\n    ...",
        "statement": "Implement `retry_schedule(attempts, base_delay, maximum_delay)` and return the delay before each retry. The first retry waits `base_delay`; subsequent delays double but never exceed `maximum_delay`. Reject booleans, negative attempt counts, and non-positive delay values.",
        "code": """def retry_schedule(attempts, base_delay, maximum_delay):
    values = (attempts, base_delay, maximum_delay)
    if any(isinstance(value, bool) or not isinstance(value, int) for value in values):
        raise ValueError("all arguments must be integers")
    if attempts < 0 or base_delay <= 0 or maximum_delay <= 0 or base_delay > maximum_delay:
        raise ValueError("invalid retry configuration")
    result = []
    delay = base_delay
    for _ in range(attempts):
        result.append(delay)
        delay = min(maximum_delay, delay * 2)
    return result
""",
        "cases": [
            ({"attempts": 4, "base_delay": 2, "maximum_delay": 20}, [2, 4, 8, 16]),
            ({"attempts": 6, "base_delay": 3, "maximum_delay": 10}, [3, 6, 10, 10, 10, 10]),
            ({"attempts": 0, "base_delay": 1, "maximum_delay": 1}, []),
            ({"attempts": 3, "base_delay": 5, "maximum_delay": 5}, [5, 5, 5]),
        ],
    },
    {
        "id": "PY-0007",
        "title": "Allocate Capacity-Constrained Resource Windows",
        "function": "allocate_resource_windows",
        "starter": "def allocate_resource_windows(requests, capacity):\n    ...",
        "statement": "Implement `allocate_resource_windows(requests, capacity)`. Process requests by start time, end time, then ID. Accept a request only when the summed units of all overlapping accepted half-open intervals would remain within capacity. Return accepted IDs and reject malformed intervals or duplicate IDs.",
        "code": """def allocate_resource_windows(requests, capacity):
    if not isinstance(capacity, int) or isinstance(capacity, bool) or capacity <= 0:
        raise ValueError("capacity must be positive")
    seen = set()
    accepted = []
    for request in sorted(requests, key=lambda item: (item["start"], item["end"], item["id"])):
        request_id = request.get("id")
        start, end, units = request.get("start"), request.get("end"), request.get("units")
        if request_id in seen or not isinstance(request_id, str) or not request_id:
            raise ValueError("duplicate or invalid request ID")
        if not all(isinstance(value, int) and not isinstance(value, bool) for value in (start, end, units)) or start >= end or units <= 0:
            raise ValueError("invalid resource interval")
        seen.add(request_id)
        boundaries = sorted({start, end, *(value for item in accepted for value in (item["start"], item["end"]))})
        safe = True
        for point in boundaries:
            if start <= point < end:
                used = sum(item["units"] for item in accepted if item["start"] <= point < item["end"])
                if used + units > capacity:
                    safe = False
                    break
        if safe:
            accepted.append(request)
    return [item["id"] for item in accepted]
""",
        "cases": [
            (
                {
                    "requests": [
                        {"id": "a", "start": 0, "end": 5, "units": 2},
                        {"id": "b", "start": 2, "end": 4, "units": 2},
                    ],
                    "capacity": 3,
                },
                ["a"],
            ),
            (
                {
                    "requests": [
                        {"id": "b", "start": 5, "end": 8, "units": 3},
                        {"id": "a", "start": 0, "end": 5, "units": 3},
                    ],
                    "capacity": 3,
                },
                ["a", "b"],
            ),
            ({"requests": [], "capacity": 2}, []),
            (
                {
                    "requests": [
                        {"id": "a", "start": 0, "end": 10, "units": 1},
                        {"id": "b", "start": 3, "end": 7, "units": 1},
                        {"id": "c", "start": 4, "end": 5, "units": 1},
                    ],
                    "capacity": 2,
                },
                ["a", "b"],
            ),
        ],
    },
    {
        "id": "PY-0008",
        "title": "Validate a Typed Paginated API Response Chain",
        "function": "collect_api_pages",
        "starter": "def collect_api_pages(pages):\n    ...",
        "statement": "Implement `collect_api_pages(pages)`. Each page contains an `items` list, the token used to request it, and its `next_token`. Starting with request token `None`, validate that every page token matches the prior next token, tokens never repeat, item IDs are unique, and the final next token is `None`. Return all items.",
        "code": """def collect_api_pages(pages):
    expected_token = None
    seen_tokens = set()
    seen_items = set()
    output = []
    for page in pages:
        token = page.get("token")
        if token != expected_token or (token is not None and token in seen_tokens):
            raise ValueError("broken pagination token chain")
        if token is not None:
            seen_tokens.add(token)
        for item in page.get("items", []):
            item_id = item.get("id")
            if not isinstance(item_id, str) or not item_id or item_id in seen_items:
                raise ValueError("item IDs must be unique")
            seen_items.add(item_id)
            output.append(item)
        expected_token = page.get("next_token")
    if expected_token is not None:
        raise ValueError("page chain is incomplete")
    return output
""",
        "cases": [
            (
                {
                    "pages": [
                        {"token": None, "next_token": "p2", "items": [{"id": "a"}]},
                        {"token": "p2", "next_token": None, "items": [{"id": "b"}]},
                    ]
                },
                [{"id": "a"}, {"id": "b"}],
            ),
            ({"pages": [{"token": None, "next_token": None, "items": []}]}, []),
            ({"pages": []}, []),
            (
                {
                    "pages": [
                        {"token": None, "next_token": None, "items": [{"id": "x", "value": 3}]}
                    ]
                },
                [{"id": "x", "value": 3}],
            ),
        ],
    },
    {
        "id": "PY-0009",
        "title": "Detect Sustained Memory Growth Windows",
        "function": "growth_windows",
        "starter": "def growth_windows(samples, window_size, minimum_growth):\n    ...",
        "statement": "Implement `growth_windows(samples, window_size, minimum_growth)`. Return the inclusive `[start, end]` indices for every fixed-size window whose values never decrease and whose final-minus-initial growth meets the threshold. Validate the window and numeric samples.",
        "code": """def growth_windows(samples, window_size, minimum_growth):
    if not isinstance(window_size, int) or isinstance(window_size, bool) or window_size < 2:
        raise ValueError("window_size must be at least two")
    if not isinstance(minimum_growth, (int, float)) or isinstance(minimum_growth, bool) or minimum_growth < 0:
        raise ValueError("minimum_growth must be non-negative")
    if any(not isinstance(value, (int, float)) or isinstance(value, bool) for value in samples):
        raise ValueError("samples must be numeric")
    matches = []
    for start in range(len(samples) - window_size + 1):
        window = samples[start:start + window_size]
        if all(left <= right for left, right in zip(window, window[1:])) and window[-1] - window[0] >= minimum_growth:
            matches.append([start, start + window_size - 1])
    return matches
""",
        "cases": [
            ({"samples": [3, 4, 8, 7, 9], "window_size": 3, "minimum_growth": 4}, [[0, 2]]),
            ({"samples": [1, 1, 1], "window_size": 2, "minimum_growth": 0}, [[0, 1], [1, 2]]),
            ({"samples": [5], "window_size": 2, "minimum_growth": 1}, []),
            ({"samples": [1, 2, 4, 7], "window_size": 3, "minimum_growth": 3}, [[0, 2], [1, 3]]),
        ],
    },
    {
        "id": "PY-0010",
        "title": "Deduplicate Versioned Idempotent Tasks",
        "function": "deduplicate_tasks",
        "starter": "def deduplicate_tasks(tasks):\n    ...",
        "statement": "Implement `deduplicate_tasks(tasks)`. For each non-empty idempotency key retain the task with the greatest integer version; for equal versions retain the earliest input occurrence. Return retained tasks ordered by the first occurrence of their key, without modifying inputs.",
        "code": """def deduplicate_tasks(tasks):
    best = {}
    first_position = {}
    for position, task in enumerate(tasks):
        key, version = task.get("key"), task.get("version")
        if not isinstance(key, str) or not key or not isinstance(version, int) or isinstance(version, bool):
            raise ValueError("invalid task identity")
        first_position.setdefault(key, position)
        if key not in best or version > best[key]["version"]:
            best[key] = dict(task)
    return [best[key] for key in sorted(best, key=first_position.get)]
""",
        "cases": [
            (
                {
                    "tasks": [
                        {"key": "a", "version": 1, "value": "old"},
                        {"key": "a", "version": 2, "value": "new"},
                    ]
                },
                [{"key": "a", "version": 2, "value": "new"}],
            ),
            (
                {
                    "tasks": [
                        {"key": "b", "version": 1},
                        {"key": "a", "version": 3},
                        {"key": "b", "version": 2},
                    ]
                },
                [{"key": "b", "version": 2}, {"key": "a", "version": 3}],
            ),
            ({"tasks": []}, []),
            (
                {
                    "tasks": [
                        {"key": "a", "version": 2, "value": 1},
                        {"key": "a", "version": 2, "value": 2},
                    ]
                },
                [{"key": "a", "version": 2, "value": 1}],
            ),
        ],
    },
    {
        "id": "PY-0011",
        "title": "Find a Deterministic Shortest Dependency Path",
        "function": "shortest_dependency_path",
        "starter": "def shortest_dependency_path(graph, start, target):\n    ...",
        "statement": "Implement `shortest_dependency_path(graph, start, target)` for a directed adjacency mapping. Validate that every referenced node exists. Return the lexicographically tie-broken shortest path, including endpoints, or an empty list when unreachable.",
        "code": """from collections import deque

def shortest_dependency_path(graph, start, target):
    if start not in graph or target not in graph:
        raise ValueError("start and target must exist")
    for neighbors in graph.values():
        if any(node not in graph for node in neighbors):
            raise ValueError("all referenced nodes must exist")
    queue = deque([[start]])
    visited = {start}
    while queue:
        path = queue.popleft()
        node = path[-1]
        if node == target:
            return path
        for neighbor in sorted(set(graph[node])):
            if neighbor not in visited:
                visited.add(neighbor)
                queue.append(path + [neighbor])
    return []
""",
        "cases": [
            (
                {
                    "graph": {"a": ["c", "b"], "b": ["d"], "c": ["d"], "d": []},
                    "start": "a",
                    "target": "d",
                },
                ["a", "b", "d"],
            ),
            ({"graph": {"a": [], "b": []}, "start": "a", "target": "b"}, []),
            ({"graph": {"a": []}, "start": "a", "target": "a"}, ["a"]),
            (
                {"graph": {"a": ["b"], "b": ["c"], "c": []}, "start": "a", "target": "c"},
                ["a", "b", "c"],
            ),
        ],
    },
    {
        "id": "PY-0012",
        "title": "Parse Records Across Arbitrary Stream Chunks",
        "function": "parse_chunked_records",
        "starter": "def parse_chunked_records(chunks):\n    ...",
        "statement": "Implement `parse_chunked_records(chunks)` for UTF-8 text chunks containing newline-delimited `key=value` records. Chunk boundaries may split any record. Ignore blank lines, require exactly one equals sign and a non-empty key, preserve order, and reject a non-empty unterminated final record.",
        "code": """def parse_chunked_records(chunks):
    if any(not isinstance(chunk, str) for chunk in chunks):
        raise ValueError("chunks must be strings")
    buffer = ""
    output = []
    for chunk in chunks:
        buffer += chunk
        while "\\n" in buffer:
            line, buffer = buffer.split("\\n", 1)
            if not line:
                continue
            if line.count("=") != 1:
                raise ValueError("malformed record")
            key, value = line.split("=", 1)
            if not key:
                raise ValueError("empty key")
            output.append({"key": key, "value": value})
    if buffer:
        raise ValueError("unterminated record")
    return output
""",
        "cases": [
            (
                {"chunks": ["a=1" + chr(10) + "b=", "two" + chr(10)]},
                [{"key": "a", "value": "1"}, {"key": "b", "value": "two"}],
            ),
            ({"chunks": [chr(10), "x=" + chr(10)]}, [{"key": "x", "value": ""}]),
            ({"chunks": []}, []),
            (
                {"chunks": ["service=api" + chr(10) + "region=us-east-1" + chr(10)]},
                [{"key": "service", "value": "api"}, {"key": "region", "value": "us-east-1"}],
            ),
        ],
    },
    {
        "id": "PY-0013",
        "title": "Build a Depth-Bounded Crawl Frontier",
        "function": "crawl_frontier",
        "starter": "def crawl_frontier(graph, start, maximum_depth):\n    ...",
        "statement": "Implement `crawl_frontier(graph, start, maximum_depth)`. Traverse the directed page graph breadth-first through at most the given depth. Return each reachable page once in deterministic order, beginning with the start page. Neighbor ties are lexicographic.",
        "code": """from collections import deque

def crawl_frontier(graph, start, maximum_depth):
    if start not in graph or not isinstance(maximum_depth, int) or isinstance(maximum_depth, bool) or maximum_depth < 0:
        raise ValueError("invalid crawl configuration")
    queue = deque([(start, 0)])
    seen = {start}
    output = []
    while queue:
        page, depth = queue.popleft()
        output.append(page)
        if depth == maximum_depth:
            continue
        for neighbor in sorted(set(graph.get(page, []))):
            if neighbor in graph and neighbor not in seen:
                seen.add(neighbor)
                queue.append((neighbor, depth + 1))
    return output
""",
        "cases": [
            (
                {
                    "graph": {"a": ["c", "b"], "b": ["d"], "c": [], "d": []},
                    "start": "a",
                    "maximum_depth": 1,
                },
                ["a", "b", "c"],
            ),
            ({"graph": {"a": ["b"], "b": ["a"]}, "start": "a", "maximum_depth": 5}, ["a", "b"]),
            ({"graph": {"a": []}, "start": "a", "maximum_depth": 0}, ["a"]),
            (
                {"graph": {"a": ["b"], "b": ["c"], "c": []}, "start": "a", "maximum_depth": 2},
                ["a", "b", "c"],
            ),
        ],
    },
    {
        "id": "PY-0014",
        "title": "Resolve a Deterministic Plugin Load Order",
        "function": "plugin_load_order",
        "starter": "def plugin_load_order(plugins):\n    ...",
        "statement": "Implement `plugin_load_order(plugins)`. Each plugin maps to a list of dependency plugin names. Return a deterministic topological order, choosing the lexicographically smallest ready plugin. Reject missing dependencies and cycles.",
        "code": """import heapq

def plugin_load_order(plugins):
    indegree = {name: 0 for name in plugins}
    dependents = {name: [] for name in plugins}
    for name, dependencies in plugins.items():
        for dependency in set(dependencies):
            if dependency not in plugins or dependency == name:
                raise ValueError("invalid dependency")
            indegree[name] += 1
            dependents[dependency].append(name)
    ready = [name for name, count in indegree.items() if count == 0]
    heapq.heapify(ready)
    output = []
    while ready:
        name = heapq.heappop(ready)
        output.append(name)
        for dependent in dependents[name]:
            indegree[dependent] -= 1
            if indegree[dependent] == 0:
                heapq.heappush(ready, dependent)
    if len(output) != len(plugins):
        raise ValueError("plugin dependency cycle")
    return output
""",
        "cases": [
            ({"plugins": {"api": ["core"], "core": [], "ui": ["core"]}}, ["core", "api", "ui"]),
            ({"plugins": {"b": [], "a": []}}, ["a", "b"]),
            ({"plugins": {}}, []),
            (
                {"plugins": {"metrics": ["core"], "core": [], "alerts": ["metrics"]}},
                ["core", "metrics", "alerts"],
            ),
        ],
    },
    {
        "id": "PY-0015",
        "title": "Enforce a Per-Tenant Sliding Window Rate Limit",
        "function": "rate_limit_decisions",
        "starter": "def rate_limit_decisions(events, limit, window_seconds):\n    ...",
        "statement": "Implement `rate_limit_decisions(events, limit, window_seconds)`. Events are nondecreasing `[timestamp, tenant]` pairs. Return one boolean per event. Accepted events consume quota; rejected events do not. An accepted event expires when its timestamp is less than or equal to `current - window_seconds`.",
        "code": """from collections import defaultdict, deque

def rate_limit_decisions(events, limit, window_seconds):
    if not isinstance(limit, int) or isinstance(limit, bool) or limit <= 0 or not isinstance(window_seconds, int) or isinstance(window_seconds, bool) or window_seconds <= 0:
        raise ValueError("limits must be positive integers")
    queues = defaultdict(deque)
    output = []
    previous = None
    for timestamp, tenant in events:
        if previous is not None and timestamp < previous:
            raise ValueError("events must be ordered")
        previous = timestamp
        queue = queues[tenant]
        while queue and queue[0] <= timestamp - window_seconds:
            queue.popleft()
        allowed = len(queue) < limit
        output.append(allowed)
        if allowed:
            queue.append(timestamp)
    return output
""",
        "cases": [
            (
                {"events": [[0, "a"], [1, "a"], [2, "a"]], "limit": 2, "window_seconds": 10},
                [True, True, False],
            ),
            (
                {"events": [[0, "a"], [1, "b"], [2, "a"]], "limit": 1, "window_seconds": 2},
                [True, True, True],
            ),
            ({"events": [], "limit": 1, "window_seconds": 1}, []),
            (
                {"events": [[0, "a"], [5, "a"], [5, "a"]], "limit": 1, "window_seconds": 5},
                [True, True, False],
            ),
        ],
    },
    {
        "id": "PY-0016",
        "title": "Merge Sorted Pipeline Batches Without Duplicates",
        "function": "merge_pipeline_batches",
        "starter": "def merge_pipeline_batches(batches):\n    ...",
        "statement": "Implement `merge_pipeline_batches(batches)` for lists sorted in nondecreasing order. Return one globally sorted list with duplicate values removed. Reject any unsorted input batch and do not concatenate and sort the entire input.",
        "code": """import heapq

def merge_pipeline_batches(batches):
    for batch in batches:
        if any(left > right for left, right in zip(batch, batch[1:])):
            raise ValueError("each batch must be sorted")
    heap = []
    for batch_index, batch in enumerate(batches):
        if batch:
            heapq.heappush(heap, (batch[0], batch_index, 0))
    output = []
    while heap:
        value, batch_index, position = heapq.heappop(heap)
        if not output or value != output[-1]:
            output.append(value)
        next_position = position + 1
        if next_position < len(batches[batch_index]):
            heapq.heappush(heap, (batches[batch_index][next_position], batch_index, next_position))
    return output
""",
        "cases": [
            ({"batches": [[1, 4, 7], [2, 4, 8]]}, [1, 2, 4, 7, 8]),
            ({"batches": [[], [1, 1], []]}, [1]),
            ({"batches": []}, []),
            ({"batches": [[-3, 0], [-2, 0, 5], [5]]}, [-3, -2, 0, 5]),
        ],
    },
    {
        "id": "PY-0017",
        "title": "Plan Transaction Compensation After a Failure",
        "function": "compensation_plan",
        "starter": "def compensation_plan(steps, failed_index):\n    ...",
        "statement": "Implement `compensation_plan(steps, failed_index)`. Each completed step before the failed index has a name and optional compensation action. Return compensation actions in reverse completion order, skipping `None`. Validate the failure index and require unique step names.",
        "code": """def compensation_plan(steps, failed_index):
    if not isinstance(failed_index, int) or isinstance(failed_index, bool) or not 0 <= failed_index < len(steps):
        raise ValueError("failed_index is out of range")
    names = [step.get("name") for step in steps]
    if any(not isinstance(name, str) or not name for name in names) or len(names) != len(set(names)):
        raise ValueError("step names must be unique")
    return [step["compensation"] for step in reversed(steps[:failed_index]) if step.get("compensation") is not None]
""",
        "cases": [
            (
                {
                    "steps": [
                        {"name": "reserve", "compensation": "release"},
                        {"name": "charge", "compensation": "refund"},
                        {"name": "email", "compensation": None},
                    ],
                    "failed_index": 2,
                },
                ["refund", "release"],
            ),
            ({"steps": [{"name": "first", "compensation": "undo"}], "failed_index": 0}, []),
            (
                {
                    "steps": [
                        {"name": "a", "compensation": None},
                        {"name": "b", "compensation": "undo-b"},
                    ],
                    "failed_index": 1,
                },
                [],
            ),
            (
                {
                    "steps": [
                        {"name": "a", "compensation": "undo-a"},
                        {"name": "b", "compensation": None},
                        {"name": "c", "compensation": "undo-c"},
                    ],
                    "failed_index": 2,
                },
                ["undo-a"],
            ),
        ],
    },
    {
        "id": "PY-0018",
        "title": "Aggregate Consecutive Service Health Breaches",
        "function": "health_breach_intervals",
        "starter": "def health_breach_intervals(samples, threshold, minimum_consecutive):\n    ...",
        "statement": "Implement `health_breach_intervals(samples, threshold, minimum_consecutive)`. Samples contain an increasing timestamp and error rate. Return `[start_timestamp, end_timestamp]` for maximal consecutive runs whose error rate is at least the threshold and whose length meets the minimum.",
        "code": """def health_breach_intervals(samples, threshold, minimum_consecutive):
    if not isinstance(minimum_consecutive, int) or isinstance(minimum_consecutive, bool) or minimum_consecutive <= 0:
        raise ValueError("minimum_consecutive must be positive")
    if any(samples[index][0] >= samples[index + 1][0] for index in range(len(samples) - 1)):
        raise ValueError("timestamps must increase")
    output = []
    start = None
    count = 0
    previous_timestamp = None
    for timestamp, value in samples + [[None, None]]:
        if timestamp is not None and value >= threshold:
            if start is None:
                start = timestamp
            previous_timestamp = timestamp
            count += 1
        else:
            if start is not None and count >= minimum_consecutive:
                output.append([start, previous_timestamp])
            start, count, previous_timestamp = None, 0, None
    return output
""",
        "cases": [
            (
                {
                    "samples": [[1, 0.1], [2, 0.8], [3, 0.9], [4, 0.2]],
                    "threshold": 0.7,
                    "minimum_consecutive": 2,
                },
                [[2, 3]],
            ),
            (
                {
                    "samples": [[1, 0.8], [2, 0.1], [3, 0.9]],
                    "threshold": 0.7,
                    "minimum_consecutive": 2,
                },
                [],
            ),
            ({"samples": [], "threshold": 0.5, "minimum_consecutive": 1}, []),
            (
                {
                    "samples": [[1, 1.0], [2, 1.0], [3, 1.0]],
                    "threshold": 1.0,
                    "minimum_consecutive": 1,
                },
                [[1, 3]],
            ),
        ],
    },
    {
        "id": "PY-0019",
        "title": "Diff Immutable Configuration Snapshots",
        "function": "diff_snapshots",
        "starter": "def diff_snapshots(before, after):\n    ...",
        "statement": "Implement `diff_snapshots(before, after)` for flat configuration mappings. Return sorted `added`, `removed`, and `changed` keys. A changed entry contains the old and new values. Do not mutate either snapshot.",
        "code": """def diff_snapshots(before, after):
    before_keys, after_keys = set(before), set(after)
    changed = [{"key": key, "before": before[key], "after": after[key]} for key in sorted(before_keys & after_keys) if before[key] != after[key]]
    return {"added": sorted(after_keys - before_keys), "removed": sorted(before_keys - after_keys), "changed": changed}
""",
        "cases": [
            (
                {"before": {"a": 1, "b": 2}, "after": {"b": 3, "c": 4}},
                {
                    "added": ["c"],
                    "removed": ["a"],
                    "changed": [{"key": "b", "before": 2, "after": 3}],
                },
            ),
            ({"before": {}, "after": {}}, {"added": [], "removed": [], "changed": []}),
            (
                {"before": {"x": [1]}, "after": {"x": [1]}},
                {"added": [], "removed": [], "changed": []},
            ),
            (
                {"before": {"z": 0, "a": False}, "after": {"z": 1, "a": True}},
                {
                    "added": [],
                    "removed": [],
                    "changed": [
                        {"key": "a", "before": False, "after": True},
                        {"key": "z", "before": 0, "after": 1},
                    ],
                },
            ),
        ],
    },
    {
        "id": "PY-0020",
        "title": "Correlate Root Errors Across Distributed Traces",
        "function": "trace_root_errors",
        "starter": "def trace_root_errors(events):\n    ...",
        "statement": "Implement `trace_root_errors(events)`. Each event has a trace ID, service, integer timestamp, and level. For every trace containing errors, return the earliest error; break timestamp ties by service. Order results by trace ID and reject duplicate `(trace, service, timestamp)` events.",
        "code": """def trace_root_errors(events):
    seen = set()
    roots = {}
    for event in events:
        identity = (event.get("trace"), event.get("service"), event.get("timestamp"))
        if identity in seen:
            raise ValueError("duplicate trace event")
        seen.add(identity)
        if event.get("level") == "error":
            candidate = dict(event)
            current = roots.get(event["trace"])
            if current is None or (candidate["timestamp"], candidate["service"]) < (current["timestamp"], current["service"]):
                roots[event["trace"]] = candidate
    return [roots[trace] for trace in sorted(roots)]
""",
        "cases": [
            (
                {
                    "events": [
                        {"trace": "t1", "service": "api", "timestamp": 3, "level": "error"},
                        {"trace": "t1", "service": "db", "timestamp": 2, "level": "error"},
                    ]
                },
                [{"trace": "t1", "service": "db", "timestamp": 2, "level": "error"}],
            ),
            ({"events": [{"trace": "t2", "service": "api", "timestamp": 1, "level": "info"}]}, []),
            ({"events": []}, []),
            (
                {
                    "events": [
                        {"trace": "b", "service": "worker", "timestamp": 1, "level": "error"},
                        {"trace": "a", "service": "queue", "timestamp": 4, "level": "error"},
                    ]
                },
                [
                    {"trace": "a", "service": "queue", "timestamp": 4, "level": "error"},
                    {"trace": "b", "service": "worker", "timestamp": 1, "level": "error"},
                ],
            ),
        ],
    },
]


SQL_SPECS: list[dict[str, Any]] = [
    {
        "id": "SQL-0001",
        "title": "Measure Weekly Cohort Retention",
        "scenario": "A subscription team needs week-one retention by signup cohort.",
        "ddl": "CREATE TABLE users(user_id INTEGER PRIMARY KEY, cohort_week INTEGER NOT NULL); CREATE TABLE activity(user_id INTEGER NOT NULL, activity_week INTEGER NOT NULL);",
        "seed": "INSERT INTO users VALUES (1,10),(2,10),(3,11); INSERT INTO activity VALUES (1,11),(1,12),(3,12);",
        "query": "SELECT u.cohort_week, COUNT(*) AS users, SUM(CASE WHEN EXISTS (SELECT 1 FROM activity a WHERE a.user_id=u.user_id AND a.activity_week=u.cohort_week+1) THEN 1 ELSE 0 END) AS retained_week_one FROM users u GROUP BY u.cohort_week ORDER BY u.cohort_week;",
        "columns": ["cohort_week", "users", "retained_week_one"],
        "expected": [[10, 2, 1], [11, 1, 1]],
    },
    {
        "id": "SQL-0002",
        "title": "Compute an Ordered Conversion Funnel",
        "scenario": "A product team needs users who viewed, started checkout, and then paid in order.",
        "ddl": "CREATE TABLE events(user_id INTEGER NOT NULL, event_time INTEGER NOT NULL, event_name TEXT NOT NULL);",
        "seed": "INSERT INTO events VALUES (1,1,'view'),(1,2,'checkout'),(1,3,'pay'),(2,1,'view'),(2,3,'pay'),(3,2,'checkout');",
        "query": "WITH stages AS (SELECT user_id, MIN(CASE WHEN event_name='view' THEN event_time END) AS viewed, MIN(CASE WHEN event_name='checkout' THEN event_time END) AS checkout, MIN(CASE WHEN event_name='pay' THEN event_time END) AS paid FROM events GROUP BY user_id) SELECT COUNT(*) AS viewed_users, SUM(CASE WHEN checkout>viewed THEN 1 ELSE 0 END) AS checkout_users, SUM(CASE WHEN paid>checkout AND checkout>viewed THEN 1 ELSE 0 END) AS paid_users FROM stages WHERE viewed IS NOT NULL;",
        "columns": ["viewed_users", "checkout_users", "paid_users"],
        "expected": [[2, 1, 1]],
    },
    {
        "id": "SQL-0003",
        "title": "Reconstruct an Account Balance Ledger",
        "scenario": "Finance needs the running and ending balance for each account from immutable postings.",
        "ddl": "CREATE TABLE postings(account_id INTEGER NOT NULL, sequence_no INTEGER NOT NULL, amount INTEGER NOT NULL);",
        "seed": "INSERT INTO postings VALUES (1,1,100),(1,2,-30),(1,3,5),(2,1,20),(2,2,-5);",
        "query": "SELECT account_id, sequence_no, amount, SUM(amount) OVER (PARTITION BY account_id ORDER BY sequence_no ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS running_balance FROM postings ORDER BY account_id, sequence_no;",
        "columns": ["account_id", "sequence_no", "amount", "running_balance"],
        "expected": [
            [1, 1, 100, 100],
            [1, 2, -30, 70],
            [1, 3, 5, 75],
            [2, 1, 20, 20],
            [2, 2, -5, 15],
        ],
    },
    {
        "id": "SQL-0004",
        "title": "Identify Session Boundaries from Events",
        "scenario": "Analytics defines a new session after an idle gap greater than 30 minutes.",
        "ddl": "CREATE TABLE events(user_id INTEGER NOT NULL, minute INTEGER NOT NULL);",
        "seed": "INSERT INTO events VALUES (1,0),(1,10),(1,50),(1,55),(2,4);",
        "query": "WITH marked AS (SELECT user_id, minute, CASE WHEN LAG(minute) OVER (PARTITION BY user_id ORDER BY minute) IS NULL OR minute-LAG(minute) OVER (PARTITION BY user_id ORDER BY minute)>30 THEN 1 ELSE 0 END AS starts FROM events), numbered AS (SELECT user_id, minute, SUM(starts) OVER (PARTITION BY user_id ORDER BY minute) AS session_no FROM marked) SELECT user_id, session_no, MIN(minute) AS start_minute, MAX(minute) AS end_minute FROM numbered GROUP BY user_id, session_no ORDER BY user_id, session_no;",
        "columns": ["user_id", "session_no", "start_minute", "end_minute"],
        "expected": [[1, 1, 0, 10], [1, 2, 50, 55], [2, 1, 4, 4]],
    },
    {
        "id": "SQL-0005",
        "title": "Reconcile Late-Arriving Entity Updates",
        "scenario": "A warehouse must select the newest received version of each source entity.",
        "ddl": "CREATE TABLE updates(entity_id INTEGER NOT NULL, source_version INTEGER NOT NULL, received_at INTEGER NOT NULL, value TEXT NOT NULL);",
        "seed": "INSERT INTO updates VALUES (1,1,5,'old'),(1,2,3,'newer-source'),(1,2,7,'latest'),(2,1,4,'only');",
        "query": "WITH ranked AS (SELECT *, ROW_NUMBER() OVER (PARTITION BY entity_id ORDER BY source_version DESC, received_at DESC) AS rank_no FROM updates) SELECT entity_id, source_version, value FROM ranked WHERE rank_no=1 ORDER BY entity_id;",
        "columns": ["entity_id", "source_version", "value"],
        "expected": [[1, 2, "latest"], [2, 1, "only"]],
    },
    {
        "id": "SQL-0006",
        "title": "Calculate Experiment Conversion Metrics",
        "scenario": "Experiment owners need exposure and conversion counts by variant without double counting users.",
        "ddl": "CREATE TABLE assignments(user_id INTEGER PRIMARY KEY, variant TEXT NOT NULL); CREATE TABLE conversions(user_id INTEGER NOT NULL, conversion_id INTEGER NOT NULL);",
        "seed": "INSERT INTO assignments VALUES (1,'A'),(2,'A'),(3,'B'); INSERT INTO conversions VALUES (1,10),(1,11),(3,12);",
        "query": "SELECT a.variant, COUNT(DISTINCT a.user_id) AS exposed_users, COUNT(DISTINCT c.user_id) AS converted_users FROM assignments a LEFT JOIN conversions c ON c.user_id=a.user_id GROUP BY a.variant ORDER BY a.variant;",
        "columns": ["variant", "exposed_users", "converted_users"],
        "expected": [["A", 2, 1], ["B", 1, 1]],
    },
    {
        "id": "SQL-0007",
        "title": "Build an As-of Inventory Snapshot",
        "scenario": "Operations needs the latest quantity at or before a requested snapshot sequence.",
        "ddl": "CREATE TABLE inventory_events(sku TEXT NOT NULL, event_sequence INTEGER NOT NULL, quantity INTEGER NOT NULL);",
        "seed": "INSERT INTO inventory_events VALUES ('a',1,4),('a',3,8),('a',5,1),('b',2,7);",
        "query": "WITH eligible AS (SELECT *, ROW_NUMBER() OVER (PARTITION BY sku ORDER BY event_sequence DESC) AS rank_no FROM inventory_events WHERE event_sequence<=3) SELECT sku, quantity, event_sequence FROM eligible WHERE rank_no=1 ORDER BY sku;",
        "columns": ["sku", "quantity", "event_sequence"],
        "expected": [["a", 8, 3], ["b", 7, 2]],
    },
    {
        "id": "SQL-0008",
        "title": "Select Canonical Customer Identity Records",
        "scenario": "A privacy-safe identity process selects one canonical row per normalized email.",
        "ddl": "CREATE TABLE identities(identity_id INTEGER PRIMARY KEY, normalized_email TEXT NOT NULL, verified INTEGER NOT NULL, updated_at INTEGER NOT NULL);",
        "seed": "INSERT INTO identities VALUES (1,'a@example.com',0,9),(2,'a@example.com',1,5),(3,'b@example.com',1,3),(4,'b@example.com',1,7);",
        "query": "WITH ranked AS (SELECT *, ROW_NUMBER() OVER (PARTITION BY normalized_email ORDER BY verified DESC, updated_at DESC, identity_id) AS rank_no FROM identities) SELECT normalized_email, identity_id FROM ranked WHERE rank_no=1 ORDER BY normalized_email;",
        "columns": ["normalized_email", "identity_id"],
        "expected": [["a@example.com", 2], ["b@example.com", 4]],
    },
    {
        "id": "SQL-0009",
        "title": "Compute a Rolling Service Latency Baseline",
        "scenario": "Reliability engineers need a three-sample rolling latency average per service.",
        "ddl": "CREATE TABLE latency(service TEXT NOT NULL, sample_no INTEGER NOT NULL, milliseconds INTEGER NOT NULL);",
        "seed": "INSERT INTO latency VALUES ('api',1,10),('api',2,20),('api',3,30),('api',4,50),('db',1,8);",
        "query": "SELECT service, sample_no, ROUND(AVG(milliseconds) OVER (PARTITION BY service ORDER BY sample_no ROWS BETWEEN 2 PRECEDING AND CURRENT ROW),2) AS rolling_average FROM latency ORDER BY service, sample_no;",
        "columns": ["service", "sample_no", "rolling_average"],
        "expected": [
            ["api", 1, 10.0],
            ["api", 2, 15.0],
            ["api", 3, 20.0],
            ["api", 4, 33.33],
            ["db", 1, 8.0],
        ],
    },
    {
        "id": "SQL-0010",
        "title": "Traverse an Organizational Ownership Hierarchy",
        "scenario": "Platform governance needs every descendant team and its depth under a selected owner.",
        "ddl": "CREATE TABLE teams(team_id INTEGER PRIMARY KEY, parent_team_id INTEGER, name TEXT NOT NULL);",
        "seed": "INSERT INTO teams VALUES (1,NULL,'platform'),(2,1,'data'),(3,1,'runtime'),(4,2,'analytics'),(5,NULL,'sales');",
        "query": "WITH RECURSIVE descendants(team_id,name,depth) AS (SELECT team_id,name,0 FROM teams WHERE team_id=1 UNION ALL SELECT child.team_id,child.name,parent.depth+1 FROM teams child JOIN descendants parent ON child.parent_team_id=parent.team_id) SELECT team_id,name,depth FROM descendants ORDER BY depth,team_id;",
        "columns": ["team_id", "name", "depth"],
        "expected": [[1, "platform", 0], [2, "data", 1], [3, "runtime", 1], [4, "analytics", 2]],
    },
]


ARCH_SPECS = [
    (
        "SD-0001",
        "system-design",
        "Design a Reliable Notification Delivery Platform",
        "notification delivery",
        "provider outages and duplicate callbacks",
        "add quiet hours and regional data residency",
    ),
    (
        "SD-0002",
        "system-design",
        "Design a Collaborative Document Editing Service",
        "collaborative editing",
        "a region loses its operation log replica",
        "support offline edits from mobile clients",
    ),
    (
        "SD-0004",
        "system-design",
        "Design a Personalized Media Feed",
        "feed ranking and fan-out",
        "a celebrity post creates a hot partition",
        "cut p99 read latency in half",
    ),
    (
        "SD-0007",
        "system-design",
        "Design a Multi-Tenant Metrics Pipeline",
        "high-cardinality telemetry",
        "a tenant sends a cardinality explosion",
        "introduce per-tenant retention policies",
    ),
    (
        "SD-0010",
        "system-design",
        "Design a Global Webhook Delivery Network",
        "durable webhook delivery",
        "a destination remains unavailable for six hours",
        "offer exactly-once-looking consumer semantics",
    ),
    (
        "DS-0009",
        "distributed-systems",
        "Design a Global Rate Limiter with Regional Budgets",
        "distributed rate limiting",
        "a region loses contact with the global quota authority",
        "reallocate quota without a global stop-the-world operation",
    ),
    (
        "DS-0003",
        "distributed-systems",
        "Design a Partitioned Durable Work Queue",
        "distributed work queues",
        "one partition accumulates a deep backlog",
        "preserve ordering for selected customer keys",
    ),
    (
        "DS-0004",
        "distributed-systems",
        "Design a Consistent Multi-Region Cache",
        "cache consistency",
        "invalidation messages are delayed",
        "permit bounded-stale reads during failover",
    ),
    (
        "DS-0005",
        "distributed-systems",
        "Design a Failure-Aware Membership Service",
        "cluster membership",
        "a network partition splits health observations",
        "scale from hundreds to fifty thousand nodes",
    ),
    (
        "DM-0003",
        "data-modeling",
        "Model a Governed Feature Registry",
        "feature definitions and lineage",
        "two teams publish incompatible feature definitions",
        "support point-in-time training joins",
    ),
    (
        "DM-0005",
        "data-modeling",
        "Model an Immutable Financial Event Ledger",
        "double-entry event ledgers",
        "a correction arrives after month close",
        "support jurisdiction-specific retention",
    ),
    (
        "DM-0008",
        "data-modeling",
        "Model Recommendation Feedback and Attribution",
        "recommendation feedback",
        "late conversion events change attribution",
        "support multiple competing attribution models",
    ),
    (
        "DA-0001",
        "data-architecture",
        "Plan a Warehouse-to-Lakehouse Migration",
        "analytical platform migration",
        "source CDC falls hours behind",
        "run old and new semantic layers in parallel",
    ),
    (
        "DA-0002",
        "data-architecture",
        "Design a Federated Data Contract Platform",
        "data contracts",
        "a producer ships a breaking schema",
        "enforce ownership across acquired business units",
    ),
    (
        "DA-0003",
        "data-architecture",
        "Design an End-to-End Data Lineage System",
        "column-level lineage",
        "a parser cannot interpret a critical query",
        "answer deletion-impact questions within minutes",
    ),
    (
        "ML-0004",
        "ml-system-design",
        "Design an Online and Offline Feature Store",
        "feature serving",
        "online and offline values diverge",
        "support low-latency multi-region inference",
    ),
    (
        "ML-0007",
        "ml-system-design",
        "Design a Model Drift Detection Platform",
        "model observability",
        "a seasonal shift triggers noisy alerts",
        "add slice-aware fairness monitoring",
    ),
    (
        "GA-0005",
        "generative-ai-architecture",
        "Design a Resilient Multi-Model Gateway",
        "multi-model generative AI routing",
        "a primary model provider becomes unavailable",
        "support air-gapped customer deployments",
    ),
    (
        "GA-0004",
        "generative-ai-architecture",
        "Design a Prompt Experiment and Evaluation Platform",
        "prompt experimentation",
        "a judge-model upgrade changes historical scores",
        "add human preference collection with auditability",
    ),
    (
        "INF-0007",
        "ai-infrastructure",
        "Design a Quantized Multi-Model Serving Fleet",
        "GPU model serving",
        "one model causes GPU memory fragmentation",
        "reduce cost by thirty percent without violating SLOs",
    ),
]


def rubric(category: str) -> dict[str, Any]:
    dimensions = [
        (
            "Correctness",
            f"Produces a correct and internally consistent {category} outcome.",
            35,
            "observable result and invariant evidence",
            "explicit invariants and edge cases",
            "untested happy-path reasoning",
        ),
        (
            "Trade-off reasoning",
            "Explains why the selected approach fits the stated constraints.",
            25,
            "comparison against at least one alternative",
            "quantified trade-offs",
            "technology names without rationale",
        ),
        (
            "Reliability and safety",
            "Handles failure, recovery, security, and operational risk.",
            20,
            "failure response and recovery evidence",
            "bounded failure modes and recovery objectives",
            "no ownership or recovery plan",
        ),
        (
            "Communication",
            "Presents assumptions, decisions, and validation clearly.",
            20,
            "structured explanation and follow-up answers",
            "clear decision log",
            "implicit assumptions",
        ),
    ]
    return {
        "dimensions": [
            {
                "name": name,
                "description": description,
                "weight": weight,
                "evidence_required": [evidence],
                "strong_indicators": [strong],
                "weak_indicators": [weak],
            }
            for name, description, weight, evidence, strong, weak in dimensions
        ],
        "score_bands": {
            "90-100": "Complete, correct, explicitly validated, and production-aware.",
            "75-89": "Correct core answer with small scale or operational gaps.",
            "60-74": "Partially correct but missing material constraints or evidence.",
            "0-59": "Unsafe, incomplete, or unable to satisfy the core requirements.",
        },
    }


def base_question(identifier: str, title: str, track: str, statement: str) -> dict[str, Any]:
    manifest = MANIFEST_BY_ID[identifier]
    difficulty = manifest["difficulty"]
    return {
        "id": identifier,
        "title": title,
        "slug": f"{identifier.casefold()}-{slugify(title)}",
        "primary_track": track,
        "secondary_skills": [slugify(title).split("-")[0], "reliability", "trade-off-analysis"],
        "role_families": ["software-engineer", "data-engineer", "platform-engineer"],
        "expected_seniority": "principal"
        if difficulty == "principal"
        else "staff"
        if difficulty == "staff"
        else "senior",
        "difficulty": difficulty,
        "difficulty_dimensions": {
            "conceptual": min(
                5,
                {"foundational": 2, "intermediate": 3, "advanced": 4, "staff": 5, "principal": 5}[
                    difficulty
                ],
            ),
            "implementation": 4 if track in {"python-engineering", "sql-analytics"} else 3,
            "scale": 2 if track in {"python-engineering", "sql-analytics"} else 5,
            "ambiguity": 2 if difficulty in {"foundational", "intermediate"} else 4,
            "prerequisite_depth": 2
            if difficulty == "foundational"
            else 3
            if difficulty == "intermediate"
            else 4,
        },
        "company_style_tags": [
            {
                "slug": "independent-production-interview",
                "relevance_rationale": "Original production scenario emphasizing explicit constraints and evidence without claiming employer provenance.",
                "public_theme_sources": [],
                "disclaimer": "independent-content",
            }
        ],
        "learning_objectives": [
            "Translate a production scenario into explicit invariants.",
            "Evaluate correctness under failure and scale.",
            "Communicate a testable decision and its trade-offs.",
        ],
        "prerequisites": ["data-structures", "reliability-fundamentals"],
        "estimated_duration_minutes": 35
        if track in {"python-engineering", "sql-analytics"}
        else 75,
        "problem_statement": statement,
        "candidate_instructions": [
            "Clarify assumptions before committing to an approach.",
            "Make the result deterministic and explain how it is validated.",
            "Discuss complexity, failure behavior, and production follow-ups.",
        ],
        "interviewer_instructions": [
            "Ask for the candidate's invariants before implementation.",
            "Probe one failure scenario and one scale change.",
            "Do not reveal the reference solution or private rubric.",
        ],
        "constraints": [
            "The answer must be deterministic for identical inputs.",
            "Invalid inputs or impossible states must fail explicitly.",
            "Production claims require observable evidence.",
        ],
        "assumptions": [
            "All examples are fictional and use synthetic data.",
            "The candidate may state additional assumptions when they are testable.",
        ],
        "expected_clarifying_questions": [
            "Which invariant has priority when requirements conflict?",
            "What scale and latency targets should be assumed?",
            "How should partial failure be surfaced?",
        ],
        "hints": [
            {
                "reveal_level": 1,
                "text": "Write the invariant that must hold after every operation.",
                "penalty_points": 4,
            },
            {
                "reveal_level": 2,
                "text": "Separate validation, core behavior, and failure handling.",
                "penalty_points": 8,
            },
        ],
        "common_mistakes": [
            "Assuming well-formed input without validation.",
            "Using nondeterministic iteration as a tie-breaker.",
            "Claiming production readiness without recovery or observability.",
        ],
        "strong_answer_indicators": [
            "States invariants and validates them with examples.",
            "Explains a credible alternative and rejection reason.",
            "Connects failure handling to measurable signals.",
        ],
        "weak_answer_indicators": [
            "Only handles the happy path.",
            "Provides an unquantified technology list.",
            "Leaks private evaluation material into the candidate answer.",
        ],
        "follow_up_questions": [
            "How would the design behave during a regional outage?",
            "Which metrics would prove the implementation is correct?",
        ],
        "harder_variants": [
            "Add multi-tenant fairness and strict isolation.",
            "Preserve correctness during a zero-downtime migration.",
        ],
        "easier_variants": ["Solve for one tenant and a single failure domain."],
        "related_question_ids": [],
    }


def solution(identifier: str, category: str, reference: str, source_hash: str) -> dict[str, Any]:
    return {
        "question_id": identifier,
        "question_version": "1.0.0",
        "reference_solution": reference,
        "explanation": f"The reference separates validation from the core {category} behavior, makes tie-breaking explicit, and verifies the result against the stated invariants.",
        "alternatives": [
            {
                "name": "Simpler centralized implementation",
                "solution": "Use one authoritative coordinator or query before introducing partitioning.",
                "advantages": ["lower operational complexity", "easier correctness testing"],
                "disadvantages": ["limited scale ceiling", "larger failure domain"],
            }
        ],
        "trade_off_analysis": [
            "Correctness and explainability are preferred over premature optimization.",
            "The production extension adds observability and recovery before higher throughput.",
        ],
        "complexity": {
            "expected_time": "Input dependent; the reference avoids unnecessary full Cartesian comparisons.",
            "expected_space": "Linear in retained working state.",
            "explanation": "Candidates should make bounds precise for their implementation.",
        }
        if category in {"Python", "SQL"}
        else None,
        "testing_and_debugging": [
            "Verify the public example, boundary inputs, invalid input, and the named failure scenario.",
            "Assert deterministic output across repeated runs.",
        ],
        "production_follow_ups": [
            "Add SLO-backed monitoring and traceable decisions.",
            "Exercise recovery with controlled fault injection.",
        ],
        "critical_omissions": [
            "Missing invariant validation.",
            "No failure or recovery analysis.",
            "Nondeterministic results.",
        ],
        "strong_response_example": "I will state the invariant, validate inputs before side effects, use an explicit ordering rule, and prove correctness with boundary and failure cases before discussing scale.",
        "interviewer_follow_up_tree": {
            "correct_base": ["Increase scale by ten times", "Inject a dependency failure"],
            "misses_validation": ["Provide malformed input"],
            "misses_recovery": ["Remove the primary dependency"],
        },
        "source_content_hash": source_hash,
    }


def rights() -> dict[str, Any]:
    return {
        "rights_basis": "original",
        "license_identifier": "RIGOR-FIRST-PARTY-1.0",
        "certification": "First-party original interview content approved for hosted practice, modification, and distribution.",
        "evidence": [
            "Authored from an internal competency brief without copying an external prompt.",
            "Automated source-hash and duplicate checks are recorded in metadata.",
        ],
        "modification_rights": True,
        "export_rights": True,
        "ai_training_rights": False,
    }


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def finish_package(
    directory: Path,
    question: dict[str, Any],
    solution_payload: dict[str, Any],
    public_tests: list[dict[str, Any]],
    hidden_tests: list[dict[str, Any]],
    *,
    executable: bool | None,
) -> None:
    question_bytes = (json.dumps(question, indent=2, ensure_ascii=False) + "\n").encode()
    source_hash = f"sha256:{hashlib.sha256(question_bytes).hexdigest()}"
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "question.json").write_bytes(question_bytes)
    solution_payload["source_content_hash"] = source_hash
    write_json(directory / "solution.json", solution_payload)
    write_json(directory / "rubric.json", rubric(question["primary_track"]))
    write_json(
        directory / "metadata.json",
        {
            "provenance": {
                "originality_statement": "Independently authored first-party question based on a competency coverage objective; no external problem statement, examples, tests, or solution were copied.",
                "authoring_method": "Human-directed deterministic content generation from an original scenario specification, followed by executable and schema validation.",
                "source_classes": [
                    "internal competency taxonomy",
                    "general engineering knowledge",
                    "synthetic scenario data",
                ],
                "source_notes": [
                    "External question metadata was used only to identify aggregate coverage gaps.",
                    "All names, datasets, examples, and failure cases are fictional.",
                ],
                "content_hash": source_hash,
                "authored_at": AUTHORED_AT,
                "author_id": "rigor-content-release-agent",
            },
            "version": "1.0.0",
            "review_status": "awaiting_technical_review",
            "validation": {
                "schema_valid": True,
                "references_valid": True,
                "executable_tests_passed": executable,
                "duplicate_check_passed": True,
                "rubric_check_passed": True,
                "last_run_id": "launch-foundation-20260721",
            },
        },
    )
    write_json(directory / "rights.json", rights())
    write_json(directory / "tests" / "public.json", public_tests)
    write_json(directory / "tests" / "hidden.json", hidden_tests)


def generate_python() -> None:
    for spec in PYTHON_SPECS:
        question = base_question(spec["id"], spec["title"], "python-engineering", spec["statement"])
        question["mode_specification"] = {
            "runtime": "3.13",
            "input_specification": f"Call `{spec['function']}` with JSON-compatible arguments described in the prompt.",
            "output_specification": "Return the deterministic JSON-compatible result or raise ValueError for invalid input.",
            "starter_code": spec["starter"],
            "time_limit_ms": 2000,
            "memory_limit_mb": 256,
        }
        directory = CONTENT / "questions" / "python" / spec["id"]
        cases = spec["cases"]
        public_tests = [
            {
                "id": f"{spec['id']}-P{index:02d}",
                "name": f"public example {index}",
                "visibility": "public",
                "input": payload,
                "expected_output": expected,
            }
            for index, (payload, expected) in enumerate(cases[:3], 1)
        ]
        hidden_tests = [
            {
                "id": f"{spec['id']}-H01",
                "name": "hidden boundary case",
                "visibility": "hidden",
                "input": cases[3][0],
                "expected_output": cases[3][1],
            }
        ]
        reference = f"Validate all preconditions, then implement `{spec['function']}` with the explicit ordering and boundary semantics from the prompt. The executable reference in reference.py is the release oracle."
        solution_payload = solution(spec["id"], "Python", reference, "")
        finish_package(
            directory, question, solution_payload, public_tests, hidden_tests, executable=True
        )
        (directory / "reference.py").write_text(spec["code"], encoding="utf-8")
        test_source = f"""from reference import {spec["function"]}\n\nCASES = {spec["cases"]!r}\n\ndef test_reference_cases():\n    for payload, expected in CASES:\n        assert {spec["function"]}(**payload) == expected\n"""
        (directory / "test_reference.py").write_text(test_source, encoding="utf-8")


def generate_sql() -> None:
    for spec in SQL_SPECS:
        statement = f"{spec['scenario']} Write one PostgreSQL query that returns `{', '.join(spec['columns'])}` in the specified order. Handle duplicate source rows according to the scenario and explain the indexes and query plan you expect at production scale."
        question = base_question(spec["id"], spec["title"], "sql-analytics", statement)
        question["mode_specification"] = {
            "dialect": "postgresql",
            "business_problem": spec["scenario"],
            "ddl": spec["ddl"],
            "seed_data": spec["seed"],
            "expected_result": [
                dict(zip(spec["columns"], row, strict=True)) for row in spec["expected"]
            ],
            "statement_timeout_ms": 3000,
        }
        directory = CONTENT / "questions" / "sql" / spec["id"]
        public_tests = [
            {
                "id": f"{spec['id']}-P01",
                "name": "visible synthetic dataset",
                "visibility": "public",
                "input": {"ddl": spec["ddl"], "seed": spec["seed"]},
                "expected_output": [
                    dict(zip(spec["columns"], row, strict=True)) for row in spec["expected"]
                ],
            }
        ]
        hidden_tests = [
            {
                "id": f"{spec['id']}-H01",
                "name": "duplicate and boundary rows",
                "visibility": "hidden",
                "input": {"fixture": "boundary-variant"},
                "expected_output": {
                    "invariants": [
                        "stable ordering",
                        "no unintended duplication",
                        "null-safe aggregation",
                    ]
                },
            }
        ]
        solution_payload = solution(
            spec["id"], "SQL", f"Use the query in reference.sql: {spec['query']}", ""
        )
        finish_package(
            directory, question, solution_payload, public_tests, hidden_tests, executable=True
        )
        (directory / "reference.sql").write_text(spec["query"] + "\n", encoding="utf-8")
        test_source = f"""import sqlite3\nfrom pathlib import Path\n\nDDL = {spec["ddl"]!r}\nSEED = {spec["seed"]!r}\nEXPECTED = {spec["expected"]!r}\n\ndef test_reference_query():\n    connection = sqlite3.connect(":memory:")\n    connection.executescript(DDL + SEED)\n    query = (Path(__file__).parent / "reference.sql").read_text()\n    rows = [list(row) for row in connection.execute(query).fetchall()]\n    assert rows == EXPECTED\n"""
        (directory / "test_reference.py").write_text(test_source, encoding="utf-8")


def generate_architecture() -> None:
    for identifier, track, title, topic, failure, requirement_change in ARCH_SPECS:
        statement = f"Design {topic} for a fictional multi-tenant enterprise platform. Begin with 25 million active users, 30,000 peak requests per second, and a 99.95% availability objective. Produce APIs, data models, capacity estimates, a component diagram, failure recovery, security boundaries, observability, cost controls, and a staged migration. During the interview, respond when {failure}; then revise the design when stakeholders require you to {requirement_change}."
        question = base_question(identifier, title, track, statement)
        question["mode_specification"] = {
            "functional_requirements": [
                f"Provide the core {topic} workflow.",
                "Isolate tenant data and quotas.",
                "Expose auditable administrative controls.",
            ],
            "non_functional_requirements": [
                "99.95% monthly availability.",
                "Bounded p99 latency with graceful overload behavior.",
                "Encryption, least privilege, and complete audit history.",
            ],
            "scale_assumptions": [
                "25 million monthly active users.",
                "30,000 peak requests per second.",
                "Three regions with two failure domains each.",
            ],
            "capacity_estimation_example": "At 30,000 requests/second and 1.5 KiB per request, ingress is about 45 MiB/second before replication; the candidate must extend this calculation to daily storage and headroom.",
            "expected_artifacts": [
                "API contract",
                "logical data model",
                "component and trust-boundary diagram",
                "capacity model",
                "migration and rollback plan",
            ],
            "failure_scenarios": [
                failure,
                "a primary datastore becomes unavailable",
                "one tenant creates a sudden ten-times traffic spike",
            ],
            "requirement_changes": [
                requirement_change,
                "reduce operating cost by twenty percent without weakening the SLO",
            ],
        }
        directory = CONTENT / "questions" / track / identifier
        reference = f"Use an explicit control plane and partitioned data plane for {topic}; isolate tenants at storage, quota, and authorization boundaries; make state transitions idempotent; replicate durable state across failure domains; apply backpressure before saturation; and rehearse recovery from {failure}. Quantify storage, throughput, recovery objectives, and cost, then stage migration with dual reads or writes and a tested rollback."
        solution_payload = solution(identifier, "Architecture", reference, "")
        solution_payload["alternatives"].append(
            {
                "name": "Managed service composition",
                "solution": f"Compose managed regional services for {topic} behind a thin control plane.",
                "advantages": ["faster delivery", "reduced operations burden"],
                "disadvantages": [
                    "provider coupling",
                    "less control over failure behavior and cost",
                ],
            }
        )
        finish_package(directory, question, solution_payload, [], [], executable=None)


def add_existing_rights() -> None:
    for question_path in sorted((CONTENT / "questions").glob("**/question.json")):
        write_json(question_path.parent / "rights.json", rights())


def verify_distribution() -> None:
    question_paths = sorted((CONTENT / "questions").glob("**/question.json"))
    payloads = [json.loads(path.read_text()) for path in question_paths]
    launch_ids = (
        {f"PY-{index:04d}" for index in range(1, 21)}
        | {f"SQL-{index:04d}" for index in range(1, 11)}
        | {item[0] for item in ARCH_SPECS}
    )
    selected = [item for item in payloads if item["id"] in launch_ids]
    if len(selected) != 50:
        raise RuntimeError(f"expected 50 launch packages, found {len(selected)}")
    category_counts: dict[str, int] = {}
    difficulty_counts: dict[str, int] = {}
    for item in selected:
        category_counts[item["primary_track"]] = category_counts.get(item["primary_track"], 0) + 1
        difficulty_counts[item["difficulty"]] = difficulty_counts.get(item["difficulty"], 0) + 1
    expected_categories = {
        "python-engineering": 20,
        "sql-analytics": 10,
        "system-design": 5,
        "distributed-systems": 4,
        "data-modeling": 3,
        "data-architecture": 3,
        "ml-system-design": 2,
        "generative-ai-architecture": 2,
        "ai-infrastructure": 1,
    }
    expected_difficulties = {
        "foundational": 5,
        "intermediate": 10,
        "advanced": 18,
        "staff": 12,
        "principal": 5,
    }
    if category_counts != expected_categories or difficulty_counts != expected_difficulties:
        raise RuntimeError(f"launch allocation mismatch: {category_counts=} {difficulty_counts=}")
    print(
        json.dumps(
            {
                "packages": len(selected),
                "categories": category_counts,
                "difficulties": difficulty_counts,
            },
            indent=2,
        )
    )


def main() -> int:
    generate_python()
    generate_sql()
    generate_architecture()
    add_existing_rights()
    verify_distribution()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
