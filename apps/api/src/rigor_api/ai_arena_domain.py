# ruff: noqa: I001\nfrom __future__ import annotations

from dataclasses import dataclass


_DIFFICULTY_GAIN = {"easy": 18, "medium": 28, "hard": 42}


def clamp(value: int, minimum: int, maximum: int) -> int:
    return max(minimum, min(maximum, value))


def prompt_efficiency_score(prompt: str) -> int:
    length = len(prompt.strip())
    if length == 0:
        return 0
    if length <= 900:
        return 5
    if length <= 1600:
        return 4
    if length <= 2400:
        return 2
    return 1


def performance_score(runtime_ms: int | None, budget_ms: int = 2_000) -> int:
    if runtime_ms is None or runtime_ms < 0:
        return 0
    ratio = runtime_ms / max(1, budget_ms)
    if ratio <= 0.25:
        return 15
    if ratio <= 0.5:
        return 13
    if ratio <= 1:
        return 10
    if ratio <= 1.5:
        return 5
    return 0


@dataclass(frozen=True)
class ArenaScore:
    correctness: int
    performance: int
    quality: int
    efficiency: int
    total: int


def score_arena_submission(
    *,
    public_passed: int,
    public_total: int,
    hidden_passed: int,
    hidden_total: int,
    runtime_ms: int | None,
    code_quality_score: float,
    prompt: str,
) -> ArenaScore:
    total_tests = max(0, public_total) + max(0, hidden_total)
    passed_tests = max(0, public_passed) + max(0, hidden_passed)
    correctness = round((passed_tests / total_tests) * 70) if total_tests else 0
    performance = performance_score(runtime_ms)
    quality = clamp(round(max(0.0, min(1.0, code_quality_score)) * 10), 0, 10)
    efficiency = prompt_efficiency_score(prompt)
    total = clamp(correctness + performance + quality + efficiency, 0, 100)
    return ArenaScore(
        correctness=correctness,
        performance=performance,
        quality=quality,
        efficiency=efficiency,
        total=total,
    )


def rating_contribution(*, difficulty: str, score: int) -> int:
    maximum = _DIFFICULTY_GAIN.get(difficulty.casefold(), 28)
    if score < 50:
        return 0
    bounded = clamp(score, 50, 100)
    return round(((bounded - 50) / 50) * maximum)


def rating_delta(
    *,
    difficulty: str,
    score: int,
    previous_best_score: int | None,
    first_solve: bool,
) -> int:
    current = rating_contribution(difficulty=difficulty, score=score)
    previous = (
        0
        if previous_best_score is None
        else rating_contribution(difficulty=difficulty, score=previous_best_score)
    )
    improvement = max(0, current - previous)
    first_solve_bonus = 5 if first_solve and score >= 70 else 0
    return improvement + first_solve_bonus


def tier_for_rating(rating: int) -> str:
    if rating >= 1_700:
        return "Diamond"
    if rating >= 1_450:
        return "Platinum"
    if rating >= 1_250:
        return "Gold"
    if rating >= 1_100:
        return "Silver"
    return "Bronze"
