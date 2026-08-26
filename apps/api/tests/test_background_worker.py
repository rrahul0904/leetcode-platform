from __future__ import annotations

import pytest

from rigor_api.background_worker import (
    BackgroundJobError,
    parse_background_job,
)


def test_background_job_parser_accepts_explicit_job_contract() -> None:
    job = parse_background_job('{"type":"system.ping","payload":{"source":"smoke"}}')
    assert job.job_type == "system.ping"
    assert job.payload == {"source": "smoke"}


@pytest.mark.parametrize(
    "raw",
    [
        "not-json",
        "[]",
        "{}",
        '{"type":"","payload":{}}',
        '{"type":"system.ping","payload":[]}',
    ],
)
def test_background_job_parser_rejects_untrusted_shapes(raw: str) -> None:
    with pytest.raises(BackgroundJobError):
        parse_background_job(raw)
