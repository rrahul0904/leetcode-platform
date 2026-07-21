import pytest
from pydantic import ValidationError
from rigor_question_schema.models import Rubric, RubricDimension


def test_rubric_weights_must_total_one_hundred() -> None:
    with pytest.raises(ValidationError, match="must total 100"):
        Rubric(
            dimensions=[
                RubricDimension(
                    name="correctness",
                    description="Correct result",
                    weight=90,
                    evidence_required=["tests"],
                    strong_indicators=["passes"],
                    weak_indicators=["fails"],
                )
            ],
            score_bands={"strong": "Strong"},
        )
