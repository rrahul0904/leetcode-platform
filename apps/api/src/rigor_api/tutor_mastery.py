"""Read-only learner-model projection for adaptive tutoring.

Tutor conversations are not mastery evidence. This module only reads the canonical
candidate_competency_mastery projection produced from independently evaluated
candidate evidence (for example durable coding submissions). Keeping the tutor on
that source of truth prevents ordinary chat from inflating readiness.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import Connection, text

_CURRENT_USER_SQL = "NULLIF(current_setting('rigor.user_id', true), '')::uuid"


@dataclass(frozen=True)
class TutorCompetencyMastery:
    slug: str
    name: str
    mastery: float
    confidence: float
    evidence_count: int
    last_evidence_at: datetime | None


@dataclass(frozen=True)
class TutorMasterySnapshot:
    competencies: tuple[TutorCompetencyMastery, ...] = ()

    @property
    def evidence_count(self) -> int:
        return sum(item.evidence_count for item in self.competencies)


def load_tutor_mastery_snapshot(
    connection: Connection,
    *,
    limit: int = 12,
) -> TutorMasterySnapshot:
    """Load candidate-owned mastery without exposing underlying evaluator evidence.

    RLS remains authoritative, and the explicit candidate predicate makes the
    ownership rule visible in the query as defense in depth. The tutor receives
    aggregate competency state only: no hidden tests, evaluator payloads, answer
    keys, or submission internals are projected into model context.
    """

    bounded_limit = max(1, min(limit, 50))
    rows = (
        connection.execute(
            text(
                f"""
                SELECT
                    c.slug,
                    c.name,
                    m.mastery,
                    m.confidence,
                    m.evidence_count,
                    m.last_evidence_at
                FROM candidate_competency_mastery m
                JOIN competencies c ON c.id=m.competency_id
                WHERE m.candidate_id={_CURRENT_USER_SQL}
                  AND m.evidence_count > 0
                ORDER BY m.confidence DESC, m.evidence_count DESC, c.slug ASC
                LIMIT :limit
                """
            ),
            {"limit": bounded_limit},
        )
        .mappings()
        .all()
    )
    return TutorMasterySnapshot(
        competencies=tuple(
            TutorCompetencyMastery(
                slug=str(row["slug"]),
                name=str(row["name"]),
                mastery=float(row["mastery"]),
                confidence=float(row["confidence"]),
                evidence_count=int(row["evidence_count"]),
                last_evidence_at=row["last_evidence_at"],
            )
            for row in rows
        )
    )


def mastery_focus(snapshot: TutorMasterySnapshot) -> TutorCompetencyMastery | None:
    """Return the most useful evidence-backed weakness for coaching adaptation.

    Very-low-confidence projections are intentionally ignored. A tutor may use the
    returned competency to choose a question or explanation style, but this function
    never writes evidence or mastery.
    """

    qualified = [
        item
        for item in snapshot.competencies
        if item.confidence >= 0.25 and item.evidence_count > 0
    ]
    if not qualified:
        return None
    return min(qualified, key=lambda item: (item.mastery, -item.confidence, item.slug))
