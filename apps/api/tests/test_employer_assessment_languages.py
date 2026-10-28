"""Published employer coding questions preserve explicit language and never guess SQL."""

from __future__ import annotations

import pytest
from pydantic import ValidationError
from rigor_api.employer_assessment_routes import AssessmentDraftInput, AssessmentQuestion


@pytest.mark.parametrize("language", ["python", "sql"])
def test_coding_question_round_trip_language(language: str) -> None:
    question = AssessmentQuestion.model_validate({
        "number": 1,
        "kind": "code",
        "prompt": "Write a solution that deduplicates event IDs without losing order.",
        "marks": 30,
        "options": [],
        "language": language,
    })
    blueprint = question.model_dump(mode="json")
    assert blueprint["language"] == language
    assert AssessmentQuestion.model_validate(blueprint).language == language


@pytest.mark.parametrize("invalid_language", ["javascript", "pyspark", "postgresql", "bash"])
def test_unknown_execution_language_rejected(invalid_language: str) -> None:
    with pytest.raises(ValidationError):
        AssessmentQuestion.model_validate({
            "number": 1,
            "kind": "code",
            "prompt": "Return all duplicate event IDs in ascending order.",
            "marks": 30,
            "options": [],
            "language": invalid_language,
        })


@pytest.mark.parametrize("kind", ["written", "multiple_choice"])
def test_non_coding_question_rejects_execution_language(kind: str) -> None:
    with pytest.raises(ValidationError):
        AssessmentQuestion.model_validate({
            "number": 1,
            "kind": kind,
            "prompt": "Explain which event processing policy handles retries safely.",
            "marks": 30,
            "options": ["A", "B", "C", "D"] if kind == "multiple_choice" else [],
            "language": "python",
        })


def test_legacy_coding_blueprint_remains_readable_without_language() -> None:
    question = AssessmentQuestion.model_validate({
        "number": 1,
        "kind": "code",
        "prompt": "Implement a safe deduplication algorithm for events.",
        "marks": 30,
        "options": [],
    })
    # Never silently attribute an untyped question to a grading runtime.
    assert question.language is None


def test_new_coding_draft_must_declare_language() -> None:
    with pytest.raises(ValidationError, match="New coding assessments must declare"):
        AssessmentDraftInput.model_validate({
            "slug": "python-screen",
            "title": "Python engineer code screening",
            "duration_minutes": 60,
            "questions": [{
                "number": 1,
                "kind": "code",
                "prompt": "Implement a stable event deduplication algorithm.",
                "marks": 100,
                "options": [],
            }],
        })


def test_sql_draft_retains_declared_language_in_candidate_blueprint() -> None:
    draft = AssessmentDraftInput.model_validate({
        "slug": "sql-screen",
        "title": "SQL engineer code screening",
        "duration_minutes": 60,
        "questions": [{
            "number": 1,
            "kind": "code",
            "language": "sql",
            "prompt": "Write a SQL query that finds duplicate event identifiers.",
            "marks": 100,
            "options": [],
        }],
    })
    assert draft.questions[0].language == "sql"
