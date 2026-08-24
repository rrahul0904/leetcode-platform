from __future__ import annotations

from rigor_api.execution_domain import ExecutionStatus
from rigor_api.knowledge_execution_evidence_routes import _is_passing_submit


def _row(
    *,
    status: str = ExecutionStatus.completed.value,
    public_total: int = 2,
    public_passed: int = 2,
    hidden_total: int = 2,
    hidden_passed: int = 2,
) -> dict[str, object]:
    return {
        "status": status,
        "public_total": public_total,
        "public_passed": public_passed,
        "hidden_total": hidden_total,
        "hidden_passed": hidden_passed,
    }


def test_submit_pass_requires_completed_public_and_hidden_success() -> None:
    assert _is_passing_submit(_row()) is True


def test_submit_with_hidden_failure_is_not_solved() -> None:
    assert _is_passing_submit(_row(hidden_passed=1)) is False


def test_submit_without_hidden_validation_is_not_solved() -> None:
    assert _is_passing_submit(_row(hidden_total=0, hidden_passed=0)) is False


def test_runtime_failure_is_not_solved_even_if_result_counts_look_complete() -> None:
    assert _is_passing_submit(_row(status=ExecutionStatus.failed.value)) is False


def test_public_failure_is_not_solved() -> None:
    assert _is_passing_submit(_row(public_passed=1)) is False
