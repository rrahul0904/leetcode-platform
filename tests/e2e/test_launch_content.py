from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import pytest
from rigor_api.content_sync import validate_all

ROOT = Path(__file__).resolve().parents[2]
CONTENT = ROOT / "content"
LAUNCH_IDS = (
    [f"PY-{index:04d}" for index in range(1, 21)]
    + [f"SQL-{index:04d}" for index in range(1, 11)]
    + ["SD-0001", "SD-0002", "SD-0004", "SD-0007", "SD-0010"]
    + ["DS-0003", "DS-0004", "DS-0005", "DS-0009"]
    + ["DM-0003", "DM-0005", "DM-0008"]
    + ["DA-0001", "DA-0002", "DA-0003"]
    + ["ML-0004", "ML-0007", "GA-0004", "GA-0005", "INF-0007"]
)


@pytest.mark.parametrize(
    "batch",
    [LAUNCH_IDS[position : position + 5] for position in range(0, len(LAUNCH_IDS), 5)],
    ids=[f"batch-{index}" for index in range(1, 11)],
)
def test_each_five_question_release_batch_is_valid(batch: list[str]) -> None:
    results = validate_all(CONTENT, set(batch))

    assert len(results) == 5
    assert all(result.status == "valid" for result in results), [
        (result.question_id, result.findings) for result in results if result.status != "valid"
    ]


def test_launch_allocation_is_exact() -> None:
    questions = {
        payload["id"]: payload
        for path in (CONTENT / "questions").glob("**/question.json")
        if (payload := json.loads(path.read_text()))["id"] in LAUNCH_IDS
    }

    assert len(questions) == 50
    assert Counter(item["primary_track"] for item in questions.values()) == {
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
    assert Counter(item["difficulty"] for item in questions.values()) == {
        "foundational": 5,
        "intermediate": 10,
        "advanced": 18,
        "staff": 12,
        "principal": 5,
    }
    assert all(
        (path.parent / "rights.json").exists()
        for path in (CONTENT / "questions").glob("**/question.json")
    )
