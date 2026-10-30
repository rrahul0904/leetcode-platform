"""AWS employer execution worker queue-event contract and fail-closed behavior.

These contract tests never launch untrusted code in the host process.
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from uuid import uuid4

import pytest
from rigor_api.employer_code_execution_worker import (
    employer_image_digest,
    parse_employer_event,
)
from rigor_api.execution_results import TrustedResultError


def event(execution_id: str) -> str:
    return json.dumps({
        "schema_version": 1,
        "event_type": "employer_code.requested",
        "execution_id": execution_id,
    })


def test_worker_accepts_only_dedicated_typed_employer_events() -> None:
    execution_id = uuid4()
    assert parse_employer_event(event(str(execution_id))) == execution_id


def test_employer_worker_requires_digest_pinned_runtime_images() -> None:
    sandbox = SimpleNamespace(config=SimpleNamespace(
        runner_image="registry.invalid/python@sha256:" + "a" * 64,
        sql_runner_image="registry.invalid/sql@sha256:" + "b" * 64,
        sql_postgres_image="registry.invalid/postgres@sha256:" + "c" * 64,
    ))
    assert employer_image_digest(sandbox, "runner_image") == "a" * 64
    assert employer_image_digest(sandbox, "sql_runner_image") == "b" * 64
    assert employer_image_digest(sandbox, "sql_postgres_image") == "c" * 64
    sandbox.config.sql_runner_image = "registry.invalid/sql:v1"
    with pytest.raises(TrustedResultError, match="pinned"):
        employer_image_digest(sandbox, "sql_runner_image")


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
