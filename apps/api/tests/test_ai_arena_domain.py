from __future__ import annotations

from rigor_api.ai_arena_domain import (
    prompt_efficiency_score,
    rating_delta,
    score_arena_submission,
    tier_for_rating,
)


def test_prompt_efficiency_rewards_concise_instructions() -> None:
    assert prompt_efficiency_score("use a hash set") == 5
    assert prompt_efficiency_score("x" * 1_200) == 4
    assert prompt_efficiency_score("x" * 2_000) == 2
    assert prompt_efficiency_score("") == 0


def test_score_uses_public_and_hidden_results() -> None:
    score = score_arena_submission(
        public_passed=2,
        public_total=2,
        hidden_passed=3,
        hidden_total=3,
        runtime_ms=300,
        code_quality_score=0.9,
        prompt="Preserve order with a set of values already seen.",
    )
    assert score.correctness == 70
    assert score.performance == 15
    assert score.quality == 9
    assert score.efficiency == 5
    assert score.total == 99


def test_rating_only_rewards_new_demonstrated_improvement() -> None:
    assert rating_delta(
        difficulty="hard",
        score=90,
        previous_best_score=None,
        first_solve=True,
    ) > 0
    assert rating_delta(
        difficulty="hard",
        score=90,
        previous_best_score=90,
        first_solve=False,
    ) == 0


def test_tier_thresholds_are_stable() -> None:
    assert tier_for_rating(1_000) == "Bronze"
    assert tier_for_rating(1_100) == "Silver"
    assert tier_for_rating(1_250) == "Gold"
    assert tier_for_rating(1_450) == "Platinum"
    assert tier_for_rating(1_700) == "Diamond"
