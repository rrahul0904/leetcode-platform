from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import ClassVar

from sqlalchemy import Engine, create_engine, text

logger = logging.getLogger("rigor.local-execution-metrics")


@dataclass(frozen=True)
class LocalExecutionMetricsSnapshot:
    queue_depth: int
    queue_inflight: int
    oldest_queued_seconds: float
    active_executions: int
    runner_capacity: int
    retries: int
    dead_letters: int
    controller_heartbeat_age_seconds: float
    python_runner_ready: bool
    sql_runner_ready: bool
    duration_p50_ms: float
    duration_p95_ms: float
    duration_p99_ms: float
    completed_by_status: dict[str, int]
    errors_by_category: dict[str, int]

    @property
    def runner_saturation_ratio(self) -> float:
        if self.runner_capacity <= 0:
            return 0.0
        return min(1.0, self.active_executions / self.runner_capacity)


def _number(value: object) -> float:
    if value is None:
        return 0.0
    if isinstance(value, bool):
        return float(int(value))
    if isinstance(value, (int, float)):
        return float(value)
    return float(str(value))


def _integer(value: object) -> int:
    return int(_number(value))


def collect_snapshot(engine: Engine, *, runner_capacity: int) -> LocalExecutionMetricsSnapshot:
    with engine.connect() as connection:
        summary = (
            connection.execute(
                text(
                    """
                    SELECT
                      (SELECT count(*)
                         FROM local_execution_queue
                        WHERE visible_at <= CURRENT_TIMESTAMP) AS queue_depth,
                      (SELECT count(*)
                         FROM local_execution_queue
                        WHERE visible_at > CURRENT_TIMESTAMP) AS queue_inflight,
                      COALESCE((
                        SELECT max(EXTRACT(EPOCH FROM (CURRENT_TIMESTAMP - created_at)))
                          FROM local_execution_queue
                         WHERE visible_at <= CURRENT_TIMESTAMP
                      ), 0) AS oldest_queued_seconds,
                      (SELECT count(*)
                         FROM execution_requests
                        WHERE state IN (
                          'DISPATCHING'::execution_state,
                          'RUNNING'::execution_state
                        )) AS active_executions,
                      COALESCE((
                        SELECT sum(GREATEST(attempt_count - 1, 0))
                          FROM execution_requests
                      ), 0) AS retries,
                      (SELECT count(*)
                         FROM execution_requests
                        WHERE error_category='execution_attempt_limit') AS dead_letters,
                      COALESCE((
                        SELECT EXTRACT(EPOCH FROM (CURRENT_TIMESTAMP - heartbeat_at))
                          FROM local_execution_controller_status
                         WHERE controller_key='local'
                      ), 31536000) AS controller_heartbeat_age_seconds,
                      COALESCE((
                        SELECT python_runner_ready
                          FROM local_execution_controller_status
                         WHERE controller_key='local'
                      ), false) AS python_runner_ready,
                      COALESCE((
                        SELECT sql_runner_ready
                          FROM local_execution_controller_status
                         WHERE controller_key='local'
                      ), false) AS sql_runner_ready,
                      COALESCE((
                        SELECT percentile_cont(0.50) WITHIN GROUP (ORDER BY runtime_ms)
                          FROM execution_requests
                         WHERE runtime_ms IS NOT NULL
                           AND completed_at >= CURRENT_TIMESTAMP - INTERVAL '24 hours'
                      ), 0) AS duration_p50_ms,
                      COALESCE((
                        SELECT percentile_cont(0.95) WITHIN GROUP (ORDER BY runtime_ms)
                          FROM execution_requests
                         WHERE runtime_ms IS NOT NULL
                           AND completed_at >= CURRENT_TIMESTAMP - INTERVAL '24 hours'
                      ), 0) AS duration_p95_ms,
                      COALESCE((
                        SELECT percentile_cont(0.99) WITHIN GROUP (ORDER BY runtime_ms)
                          FROM execution_requests
                         WHERE runtime_ms IS NOT NULL
                           AND completed_at >= CURRENT_TIMESTAMP - INTERVAL '24 hours'
                      ), 0) AS duration_p99_ms
                    """
                )
            )
            .mappings()
            .one()
        )
        status_rows = (
            connection.execute(
                text(
                    """
                    SELECT state::text AS label, count(*) AS total
                      FROM execution_requests
                     WHERE completed_at >= CURRENT_TIMESTAMP - INTERVAL '24 hours'
                     GROUP BY state::text
                     ORDER BY state::text
                    """
                )
            )
            .mappings()
            .all()
        )
        error_rows = (
            connection.execute(
                text(
                    """
                    SELECT COALESCE(error_category, 'none') AS label, count(*) AS total
                      FROM execution_requests
                     WHERE completed_at >= CURRENT_TIMESTAMP - INTERVAL '24 hours'
                     GROUP BY COALESCE(error_category, 'none')
                     ORDER BY COALESCE(error_category, 'none')
                    """
                )
            )
            .mappings()
            .all()
        )

    return LocalExecutionMetricsSnapshot(
        queue_depth=_integer(summary["queue_depth"]),
        queue_inflight=_integer(summary["queue_inflight"]),
        oldest_queued_seconds=_number(summary["oldest_queued_seconds"]),
        active_executions=_integer(summary["active_executions"]),
        runner_capacity=max(1, runner_capacity),
        retries=_integer(summary["retries"]),
        dead_letters=_integer(summary["dead_letters"]),
        controller_heartbeat_age_seconds=_number(
            summary["controller_heartbeat_age_seconds"]
        ),
        python_runner_ready=bool(summary["python_runner_ready"]),
        sql_runner_ready=bool(summary["sql_runner_ready"]),
        duration_p50_ms=_number(summary["duration_p50_ms"]),
        duration_p95_ms=_number(summary["duration_p95_ms"]),
        duration_p99_ms=_number(summary["duration_p99_ms"]),
        completed_by_status={
            str(row["label"]): _integer(row["total"]) for row in status_rows
        },
        errors_by_category={
            str(row["label"]): _integer(row["total"]) for row in error_rows
        },
    )


def _escape_label(value: str) -> str:
    return value.replace("\\", "\\\\").replace("\n", "\\n").replace('"', '\\"')


def render_prometheus(snapshot: LocalExecutionMetricsSnapshot) -> str:
    lines = [
        "# HELP rigor_execution_metrics_up Whether the execution metrics snapshot was collected.",
        "# TYPE rigor_execution_metrics_up gauge",
        "rigor_execution_metrics_up 1",
        "# HELP rigor_execution_queue_depth Visible durable execution messages.",
        "# TYPE rigor_execution_queue_depth gauge",
        f"rigor_execution_queue_depth {snapshot.queue_depth}",
        "# HELP rigor_execution_queue_inflight Messages hidden by an active visibility lease.",
        "# TYPE rigor_execution_queue_inflight gauge",
        f"rigor_execution_queue_inflight {snapshot.queue_inflight}",
        "# HELP rigor_execution_queue_oldest_age_seconds Age of the oldest visible message.",
        "# TYPE rigor_execution_queue_oldest_age_seconds gauge",
        f"rigor_execution_queue_oldest_age_seconds {snapshot.oldest_queued_seconds:.6f}",
        "# HELP rigor_execution_active Current dispatching and running executions.",
        "# TYPE rigor_execution_active gauge",
        f"rigor_execution_active {snapshot.active_executions}",
        "# HELP rigor_execution_runner_capacity Configured local execution parallelism.",
        "# TYPE rigor_execution_runner_capacity gauge",
        f"rigor_execution_runner_capacity {snapshot.runner_capacity}",
        "# HELP rigor_execution_runner_saturation_ratio Active executions divided by capacity.",
        "# TYPE rigor_execution_runner_saturation_ratio gauge",
        f"rigor_execution_runner_saturation_ratio {snapshot.runner_saturation_ratio:.6f}",
        "# HELP rigor_execution_retry_total Durable execution retries recorded in aggregate attempts.",
        "# TYPE rigor_execution_retry_total gauge",
        f"rigor_execution_retry_total {snapshot.retries}",
        "# HELP rigor_execution_dead_letter_total Executions exhausted by infrastructure attempt limits.",
        "# TYPE rigor_execution_dead_letter_total gauge",
        f"rigor_execution_dead_letter_total {snapshot.dead_letters}",
        "# HELP rigor_execution_controller_heartbeat_age_seconds Age of the controller heartbeat.",
        "# TYPE rigor_execution_controller_heartbeat_age_seconds gauge",
        f"rigor_execution_controller_heartbeat_age_seconds {snapshot.controller_heartbeat_age_seconds:.6f}",
        "# HELP rigor_execution_runner_ready Runner readiness reported by the controller.",
        "# TYPE rigor_execution_runner_ready gauge",
        f'rigor_execution_runner_ready{{runner="python"}} {int(snapshot.python_runner_ready)}',
        f'rigor_execution_runner_ready{{runner="sql"}} {int(snapshot.sql_runner_ready)}',
        "# HELP rigor_execution_duration_ms Recent execution latency quantiles.",
        "# TYPE rigor_execution_duration_ms gauge",
        f'rigor_execution_duration_ms{{quantile="0.50"}} {snapshot.duration_p50_ms:.6f}',
        f'rigor_execution_duration_ms{{quantile="0.95"}} {snapshot.duration_p95_ms:.6f}',
        f'rigor_execution_duration_ms{{quantile="0.99"}} {snapshot.duration_p99_ms:.6f}',
        "# HELP rigor_execution_completed_total Recent terminal executions by status.",
        "# TYPE rigor_execution_completed_total gauge",
    ]
    lines.extend(
        f'rigor_execution_completed_total{{status="{_escape_label(label)}"}} {total}'
        for label, total in snapshot.completed_by_status.items()
    )
    lines.extend(
        [
            "# HELP rigor_execution_error_total Recent terminal executions by error category.",
            "# TYPE rigor_execution_error_total gauge",
        ]
    )
    lines.extend(
        f'rigor_execution_error_total{{category="{_escape_label(label)}"}} {total}'
        for label, total in snapshot.errors_by_category.items()
    )
    return "\n".join(lines) + "\n"


class MetricsHandler(BaseHTTPRequestHandler):
    engine: ClassVar[Engine]
    runner_capacity: ClassVar[int]

    def log_message(self, format: str, *args: object) -> None:
        del format, args

    def _write(self, status: HTTPStatus, body: str, content_type: str) -> None:
        encoded = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(encoded)

    def do_GET(self) -> None:
        if self.path == "/healthz":
            try:
                with self.engine.connect() as connection:
                    connection.execute(text("SELECT 1")).scalar_one()
            except Exception:
                self._write(
                    HTTPStatus.SERVICE_UNAVAILABLE,
                    '{"status":"unavailable"}\n',
                    "application/json",
                )
                return
            self._write(HTTPStatus.OK, '{"status":"ok"}\n', "application/json")
            return
        if self.path != "/metrics":
            self._write(HTTPStatus.NOT_FOUND, "not found\n", "text/plain")
            return
        try:
            snapshot = collect_snapshot(
                self.engine,
                runner_capacity=self.runner_capacity,
            )
        except Exception as exc:
            logger.exception(
                "local_execution.metrics_failed",
                extra={
                    "component": "local-execution-metrics",
                    "event": "metrics_failed",
                    "error": exc.__class__.__name__,
                },
            )
            self._write(
                HTTPStatus.SERVICE_UNAVAILABLE,
                "# TYPE rigor_execution_metrics_up gauge\nrigor_execution_metrics_up 0\n",
                "text/plain; version=0.0.4; charset=utf-8",
            )
            return
        self._write(
            HTTPStatus.OK,
            render_prometheus(snapshot),
            "text/plain; version=0.0.4; charset=utf-8",
        )


def main() -> int:
    logging.basicConfig(level=os.getenv("RIGOR_LOG_LEVEL", "INFO"))
    database_url = os.getenv("RIGOR_METRICS_DATABASE_URL", "")
    if not database_url:
        raise RuntimeError("RIGOR_METRICS_DATABASE_URL is required.")
    host = os.getenv("RIGOR_METRICS_HOST", "0.0.0.0")
    port = int(os.getenv("RIGOR_METRICS_PORT", "9108"))
    capacity = int(os.getenv("RIGOR_LOCAL_EXECUTION_PARALLELISM", "4"))
    engine = create_engine(database_url, pool_pre_ping=True, pool_size=2, max_overflow=2)
    MetricsHandler.engine = engine
    MetricsHandler.runner_capacity = max(1, capacity)
    server = ThreadingHTTPServer((host, port), MetricsHandler)
    try:
        server.serve_forever(poll_interval=0.25)
    finally:
        server.server_close()
        engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
