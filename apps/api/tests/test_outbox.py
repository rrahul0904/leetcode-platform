from __future__ import annotations

import pytest

from rigor_api.outbox import retry_delay_seconds


def test_retry_delay_grows_exponentially_and_is_capped() -> None:
    assert retry_delay_seconds(0, jitter_ratio=1.0) == 1.0
    assert retry_delay_seconds(1, jitter_ratio=1.0) == 2.0
    assert retry_delay_seconds(2, jitter_ratio=1.0) == 4.0
    assert retry_delay_seconds(20, jitter_ratio=1.0) == 300.0


def test_retry_delay_uses_bounded_positive_jitter() -> None:
    minimum = retry_delay_seconds(3, jitter_ratio=0.0)
    maximum = retry_delay_seconds(3, jitter_ratio=1.0)

    assert minimum == 4.0
    assert maximum == 8.0


def test_retry_delay_rejects_invalid_inputs() -> None:
    with pytest.raises(ValueError):
        retry_delay_seconds(-1, jitter_ratio=0.5)
    with pytest.raises(ValueError):
        retry_delay_seconds(1, jitter_ratio=-0.1)
    with pytest.raises(ValueError):
        retry_delay_seconds(1, jitter_ratio=1.1)
