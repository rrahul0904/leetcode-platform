from __future__ import annotations

from uuid import UUID

from rigor_api.execution_controller import ExecutionController
from rigor_api.execution_results import DispatchPackage


def test_controller_logs_preserve_api_correlation_id() -> None:
    package = DispatchPackage(
        execution_id=UUID("11111111-1111-1111-1111-111111111111"),
        organization_id=None,
        candidate_id=UUID("22222222-2222-2222-2222-222222222222"),
        practice_session_id=UUID("33333333-3333-3333-3333-333333333333"),
        submission_id=None,
        question_version_id=UUID("44444444-4444-4444-4444-444444444444"),
        execution_type="RUN",
        runtime="python3.13",
        language="python",
        source_code="def solve(value): return value",
        input_payload={"tests": []},
        limits={"profile": "python-small"},
        trace_id="request-correlation-123",
        attempt_count=1,
    )

    fields = ExecutionController._package_log(package, "running")

    assert fields["trace_id"] == "request-correlation-123"
    assert fields["execution_id"] == str(package.execution_id)
    assert fields["attempt"] == 1
    assert fields["event"] == "running"
