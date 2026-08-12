from __future__ import annotations

from rigor_api.local_execution_metrics import (
    LocalExecutionMetricsSnapshot,
    render_prometheus,
)


def test_render_prometheus_covers_queue_runners_retries_and_latency() -> None:
    snapshot = LocalExecutionMetricsSnapshot(
        queue_depth=3,
        queue_inflight=2,
        oldest_queued_seconds=12.5,
        active_executions=3,
        runner_capacity=4,
        retries=7,
        dead_letters=1,
        controller_heartbeat_age_seconds=2.25,
        python_runner_ready=True,
        sql_runner_ready=False,
        duration_p50_ms=11,
        duration_p95_ms=45,
        duration_p99_ms=90,
        completed_by_status={"COMPLETED": 8, "FAILED": 2},
        errors_by_category={"none": 8, 'runner_"failure': 2},
    )

    output = render_prometheus(snapshot)

    assert "rigor_execution_queue_depth 3" in output
    assert "rigor_execution_queue_inflight 2" in output
    assert "rigor_execution_queue_oldest_age_seconds 12.500000" in output
    assert "rigor_execution_runner_saturation_ratio 0.750000" in output
    assert "rigor_execution_retry_total 7" in output
    assert "rigor_execution_dead_letter_total 1" in output
    assert 'rigor_execution_runner_ready{runner="python"} 1' in output
    assert 'rigor_execution_runner_ready{runner="sql"} 0' in output
    assert 'rigor_execution_duration_ms{quantile="0.95"} 45.000000' in output
    assert 'rigor_execution_completed_total{status="COMPLETED"} 8' in output
    assert 'rigor_execution_error_total{category="runner_\\"failure"} 2' in output
