from __future__ import annotations

from datetime import date, timedelta

from rigor_api.knowledge_progress_routes import _streaks


def test_streaks_count_consecutive_days_ending_today() -> None:
    today = date.today()

    current, longest = _streaks(
        [
            today,
            today - timedelta(days=1),
            today - timedelta(days=2),
            today - timedelta(days=5),
        ]
    )

    assert current == 3
    assert longest == 3


def test_streaks_allow_activity_yesterday_without_faking_today() -> None:
    today = date.today()

    current, longest = _streaks(
        [
            today - timedelta(days=1),
            today - timedelta(days=2),
            today - timedelta(days=3),
        ]
    )

    assert current == 3
    assert longest == 3


def test_streaks_reset_after_gap() -> None:
    today = date.today()

    current, longest = _streaks(
        [
            today - timedelta(days=3),
            today - timedelta(days=4),
            today - timedelta(days=7),
        ]
    )

    assert current == 0
    assert longest == 2


def test_streaks_deduplicate_days() -> None:
    today = date.today()

    assert _streaks([today, today, today - timedelta(days=1)]) == (2, 2)
    assert _streaks([]) == (0, 0)
