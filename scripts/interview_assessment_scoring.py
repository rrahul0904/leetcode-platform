"""Deterministic, provisional scoring for a 60-minute Level 4 DE assessment.

Do not expose interviewer_answer_key to a browser or candidate API. Written Python,
SQL and Spark questions require rubric-guided human review; LLM output must not be
used as an autonomous reject/hire decision. This module is intentionally not wired
to an unauthenticated HTTP route.
"""

from __future__ import annotations

from typing import Any


def score_level4(
    questions: list[dict[str, Any]],
    answers: dict[str, str],
    interviewer_answer_key: dict[str, str],
) -> dict[str, Any]:
    expected_ids = {str(q["number"]) for q in questions}
    if len(questions) != 16 or expected_ids != {str(n) for n in range(1, 17)}:
        raise ValueError("Expected exactly one question for each number 1 through 16")
    if set(answers) - expected_ids:
        raise ValueError("Unknown question number in answer payload")
    if set(interviewer_answer_key) != {str(n) for n in range(7, 17)}:
        raise ValueError("The complete private Snowflake key is required")
    if any(key not in {"A", "B", "C", "D"} for key in interviewer_answer_key.values()):
        raise ValueError("Invalid private answer key")
    scores: list[dict[str, Any]] = []
    mcq_score = 0
    for question in questions:
        number = int(question["number"])
        text = answers.get(str(number), "").strip()
        if number < 7:
            scores.append({
                "question_number": number,
                "status": "pending_human_review" if text else "unanswered",
                "maximum_marks": int(question["marks"]),
                "awarded_marks": None,
            })
            continue
        choice = text.upper()
        if choice and choice not in {"A", "B", "C", "D"}:
            raise ValueError(f"Q{number}: multiple-choice answer must be A, B, C or D")
        correct = bool(choice) and choice == interviewer_answer_key[str(number)]
        awarded = int(question["marks"]) if correct else 0
        mcq_score += awarded
        scores.append({
            "question_number": number,
            "status": "provisionally_scored" if choice else "unanswered",
            "maximum_marks": int(question["marks"]),
            "awarded_marks": awarded,
        })
    if sum(int(q["marks"]) for q in questions) != 100:
        raise ValueError("Invalid assessment mark total")
    return {
        "state": "pending_human_review",
        "automatically_scored_marks": mcq_score,
        "automatically_scored_maximum": 40,
        "remaining_human_review_maximum": 60,
        "total_possible_marks": 100,
        "scores": scores,
        "hiring_decision": None,
        "notes": "MCQs are provisional; six written answers need independent rubric review.",
    }
