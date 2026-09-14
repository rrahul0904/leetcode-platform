from datetime import UTC, datetime

from rigor_api.tutor_mastery import (
    TutorCompetencyMastery,
    TutorMasterySnapshot,
    mastery_focus,
)


def _mastery(
    slug: str,
    *,
    score: float,
    confidence: float,
    evidence_count: int = 2,
) -> TutorCompetencyMastery:
    return TutorCompetencyMastery(
        slug=slug,
        name=slug.replace("-", " ").title(),
        mastery=score,
        confidence=confidence,
        evidence_count=evidence_count,
        last_evidence_at=datetime(2026, 9, 12, tzinfo=UTC),
    )


def test_mastery_focus_uses_evaluated_weakness_not_low_confidence_noise() -> None:
    snapshot = TutorMasterySnapshot(
        competencies=(
            _mastery("arrays", score=0.72, confidence=0.9),
            _mastery("dynamic-programming", score=0.41, confidence=0.8),
            _mastery("graphs", score=0.10, confidence=0.1),
        )
    )

    focus = mastery_focus(snapshot)

    assert focus is not None
    assert focus.slug == "dynamic-programming"


def test_mastery_focus_requires_real_evidence_confidence() -> None:
    snapshot = TutorMasterySnapshot(
        competencies=(_mastery("graphs", score=0.1, confidence=0.1),)
    )

    assert mastery_focus(snapshot) is None
