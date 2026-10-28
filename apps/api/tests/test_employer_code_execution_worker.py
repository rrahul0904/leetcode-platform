"""AWS employer execution worker queue-event contract and fail-closed behavior.

These contract tests never launch untrusted code in the host process.
"""

from __future__ import annotations

import json
from uuid import uuid4

import pytest
from rigor_api.employer_code_execution_worker import parse_employer_event


def event(execution_id: str) -> str:
    return json.dumps({
        "schema_version": 1,
        "event_type": "employer_code.requested",
        "execution_id": execution_id,
    })


def test_worker_accepts_only_dedicated_typed_employer_events() -> None:
    execution_id = uuid4()
    assert parse_employer_event(event(str(execution_id))) == execution_id


@pytest.mark.parametrize(
    "payload",
    [
        "not-json",
        "[]",
        "{}",
        json.dumps({"schema_version": 2, "event_type": "employer_code.requested",
                    "execution_id": str(uuid4())}),
        json.dumps({"schema_version": 1, "event_type": "execution.requested",
                    "execution_id": str(uuid4())}),
        json.dumps({"schema_version": 1, "event_type": "employer_code.requested",
                    "execution_id": "not-a-uuid"}),
        json.dumps({"schema_version": 1, "event_type": "employer_code.requested",
                    "execution_id": str(uuid4()), "source_code": "do-not-send"}),
    ],
)
def test_worker_rejects_malformed_wrong_queue_and_source_bearing_events(
    payload: str,
) -> None:
    with pytest.raises(ValueError):
        parse_employer_event(payload)
