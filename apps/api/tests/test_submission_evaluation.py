from rigor_api.execution import ExecutionResult
from rigor_api.schemas import HiddenTestSummary, PublicTestResult
from rigor_api.submissions import EVALUATOR_VERSION, deterministic_evaluation


def result(*, public_passed: int, hidden_passed: int, hidden_total: int) -> ExecutionResult:
    public = [
        PublicTestResult(
            id=f"public-{index}",
            name=f"Public {index}",
            passed=index < public_passed,
            expected_output=index,
            actual_output=index if index < public_passed else None,
        )
        for index in range(2)
    ]
    return ExecutionResult(
        status=(
            "passed"
            if public_passed == len(public) and hidden_passed == hidden_total
            else "failed"
        ),
        public_results=public,
        hidden_summary=HiddenTestSummary(total=hidden_total, passed=hidden_passed),
        error_category=None,
        duration_ms=12,
        quality_signals={
            "syntax_valid": True,
            "contains_todo": False,
            "debug_print_count": 0,
            "function_count": 1,
        },
    )


def test_deterministic_evaluation_rewards_complete_correctness() -> None:
    evaluation = deterministic_evaluation(
        result(public_passed=2, hidden_passed=3, hidden_total=3)
    )

    assert evaluation["correctness_score"] == 1.0
    assert evaluation["overall_score"] == 1.0
    assert evaluation["evaluator_version"] == EVALUATOR_VERSION


def test_deterministic_evaluation_keeps_hidden_inputs_out_of_signals() -> None:
    evaluation = deterministic_evaluation(
        result(public_passed=2, hidden_passed=1, hidden_total=3)
    )

    assert evaluation["correctness_score"] == 0.6
    assert evaluation["deterministic_signals"]["hidden_total"] == 3
    assert evaluation["deterministic_signals"]["hidden_passed"] == 1
    assert "hidden_inputs" not in evaluation["deterministic_signals"]


def test_deterministic_evaluation_is_repeatable() -> None:
    execution = result(public_passed=1, hidden_passed=2, hidden_total=3)

    assert deterministic_evaluation(execution) == deterministic_evaluation(execution)
