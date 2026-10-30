"""Fail-closed provisional scoring for Level-4 DE and DevOps assessments.

This is a privileged offline function, NOT a public endpoint. Never send its
private answer key to candidates or models. Written responses require independent
human rubric review; the result MUST NOT be used for automatic hiring decisions.
"""

from __future__ import annotations

from typing import Any

PROFILES: dict[str, tuple[int, int, list[int]]] = {
    "data-engineering": (6, 16, [10, 10, 8, 8, 9, 15] + [4] * 10),
    "devops": (4, 14, [15] * 4 + [4] * 10),
}


def score_assessment(
    questions: list[dict[str, Any]],
    answers: dict[str, str],
    interviewer_answer_key: dict[str, str],
    *,
    profile: str,
) -> dict[str, Any]:
    if profile not in PROFILES:
        raise ValueError("Unknown assessment profile")
    written, count, expected_marks = PROFILES[profile]
    expected = {str(n) for n in range(1, count + 1)}
    expected_keys = {str(n) for n in range(written + 1, count + 1)}
    if len(questions) != count or [q.get("number") for q in questions] != list(
        range(1, count + 1)
    ):
        raise ValueError("Missing, duplicate or out-of-order assessment questions")
    if [
        q.get("marks") for q in questions
    ] != expected_marks:
        raise ValueError("Question point allocations do not match source contract")
    if set(answers) - expected:
        raise ValueError("Unknown answer in response")
    if set(interviewer_answer_key) != expected_keys or any(
        choice not in {"A", "B", "C", "D"} for choice in interviewer_answer_key.values()
    ):
        raise ValueError("Complete, valid privileged answer key required")
    scores: list[dict[str, Any]] = []
    mcq_total = 0
    for number in range(1, count + 1):
        raw = answers.get(str(number), "")
        if not isinstance(raw, str):
            raise ValueError(f"Q{number}: response must be text")
        response = raw.strip()
        marks = int(questions[number - 1]["marks"])
        if number <= written:
            scores.append({
                "question_number": number,
                "status": "pending_human_review" if response else "unanswered",
                "maximum_marks": marks,
                "awarded_marks": None,
            })
            continue
        option = response.upper()
        if option and option not in {"A", "B", "C", "D"}:
            raise ValueError(f"Q{number}: MCQ response must be A/B/C/D")
        awarded = marks if option and option == interviewer_answer_key[str(number)] else 0
        mcq_total += awarded
        scores.append({
            "question_number": number,
            "status": "provisionally_scored" if option else "unanswered",
            "maximum_marks": marks,
            "awarded_marks": awarded,
        })
    return {
        "state": "pending_human_review",
        "profile": profile,
        "automatically_scored_marks": mcq_total,
        "automatically_scored_maximum": 40,
        "remaining_human_review_maximum": 60,
        "total_possible_marks": 100,
        "scores": scores,
        "hiring_decision": None,
        "notes": "MCQ marks provisional; all written answers need independent human review.",
    }


def score_level4(
    questions: list[dict[str, Any]],
    answers: dict[str, str],
    interviewer_answer_key: dict[str, str],
) -> dict[str, Any]:
    """Backwards-compatible entrypoint for existing Data Engineering fixtures."""
    return score_assessment(
        questions,
        answers,
        interviewer_answer_key,
        profile="data-engineering",
    )
