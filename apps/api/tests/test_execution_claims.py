from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from rigor_api.execution_claims import validate_lease_deadline


def test_lease_deadline_must_be_timezone_aware_and_future() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        validate_lease_deadline(datetime.now())

    with pytest.raises(ValueError, match="future"):
        validate_lease_deadline(datetime.now(UTC) - timedelta(seconds=1))

    validate_lease_deadline(datetime.now(UTC) + timedelta(minutes=1))
