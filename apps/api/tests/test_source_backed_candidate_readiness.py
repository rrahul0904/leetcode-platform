from __future__ import annotations

import importlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

readiness = importlib.import_module("scripts.assess_source_backed_candidates")


def _candidate(**overrides: object) -> dict[str, object]:
    candidate: dict[str, object] = {
        "slug": "bounded-cache",
        "title": "Bounded Cache",
        "problem_markdown": "# Bounded Cache\n" + ("Build a deterministic cache. " * 12),
        "explanation_markdown": "Use a hash map and an ordered structure.",
        "reference_solution_language": "py",
        "reference_solution_code": "def solve():\n    return 1\n",
        "companies": ["Acme", "Example"],
        "topics": ["Hash Table", "Design"],
    }
    candidate.update(overrides)
    return candidate


def test_imported_candidate_stays_in_review_until_publication_contract_is_complete() -> None:
    assessment = readiness.assess_candidate(_candidate())

    assert assessment["availability"] == "in_review"
    assert assessment["language"] == "python"
    assert assessment["priority_score"] > 80
    assert set(assessment["blockers"]) == {
        "rights_not_approved",
        "starter_code_missing",
        "public_tests_missing",
        "hidden_tests_missing",
        "reference_validation_missing",
        "publication_approval_missing",
    }


def test_complete_reviewed_candidate_can_become_runnable() -> None:
    assessment = readiness.assess_candidate(
        _candidate(
            rights_disposition="hostable_licensed",
            starter_code="def solve():\n    ...\n",
            public_tests=[{"input": [], "expected_output": 1}],
            hidden_tests=[{"input": [1], "expected_output": 1}],
            reference_tests_passed=True,
            publication_approved=True,
        )
    )

    assert assessment["availability"] == "runnable"
    assert assessment["blockers"] == []


def test_review_report_prioritizes_python_candidates_and_counts_blockers() -> None:
    report = readiness.build_report(
        [
            _candidate(slug="complete", rights_disposition="hostable_licensed"),
            _candidate(
                slug="unsupported",
                reference_solution_language="java",
                explanation_markdown="",
            ),
        ],
        review_limit=1,
    )

    summary = report["summary"]
    queue = report["review_queue"]
    blockers = report["blocker_counts"]

    assert isinstance(summary, dict)
    assert isinstance(queue, list)
    assert isinstance(blockers, dict)
    assert summary["total_candidates"] == 2
    assert summary["review_queue_size"] == 1
    assert queue[0]["slug"] == "complete"
    assert blockers["runtime_unsupported"] == 1
    assert blockers["editorial_missing"] == 1
