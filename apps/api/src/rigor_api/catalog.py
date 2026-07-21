from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from .schemas import ContentStats, ManifestQuestion, Page


class ManifestCatalog:
    """Read-only Milestone 0 adapter for planned metadata.

    Candidate-facing publication will use PostgreSQL. This adapter exists to make
    foundation progress inspectable without pretending planned entries are published.
    """

    def __init__(self, manifest_path: Path) -> None:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        self._foundation_count = int(payload["foundation_milestone_count"])
        self._disclaimer = str(payload["disclaimer"])
        self._questions = [ManifestQuestion.model_validate(item) for item in payload["questions"]]

    def stats(self) -> ContentStats:
        track_counts = Counter(question.primary_track for question in self._questions)
        difficulty_counts = Counter(question.difficulty for question in self._questions)
        return ContentStats(
            foundation_manifest_entries=self._foundation_count,
            growth_model="continuous_unbounded",
            planned_questions=len(self._questions),
            complete_questions=0,
            validated_questions=0,
            published_questions=0,
            track_counts=dict(track_counts),
            difficulty_counts=dict(difficulty_counts),
            disclaimer=self._disclaimer,
        )

    def list_planned(
        self,
        *,
        page: int,
        page_size: int,
        query: str | None,
        track: str | None,
        difficulty: str | None,
    ) -> Page[ManifestQuestion]:
        items = self._questions
        if query:
            normalized = query.casefold()
            items = [
                item
                for item in items
                if normalized in item.working_title.casefold()
                or normalized in item.learning_objective.casefold()
                or any(normalized in skill.casefold() for skill in item.skills)
            ]
        if track:
            items = [item for item in items if item.primary_track == track]
        if difficulty:
            items = [item for item in items if item.difficulty == difficulty]
        total = len(items)
        start = (page - 1) * page_size
        end = start + page_size
        return Page[ManifestQuestion](
            items=items[start:end],
            page=page,
            page_size=page_size,
            total=total,
            has_next=end < total,
        )

    def get_planned_by_slug(self, slug: str) -> ManifestQuestion | None:
        return next((question for question in self._questions if question.slug == slug), None)
