from __future__ import annotations

import socket
from urllib.parse import urlparse

from sqlalchemy import Engine, text
from sqlalchemy.exc import SQLAlchemyError

from .config import Settings
from .execution_routes import (
    EXECUTION_ROUTES_REGISTERED,
    LEGACY_SYNCHRONOUS_EXECUTION_BLOCKED,
)
from .schemas import ReadinessCheck, ReadinessResponse

EXPECTED_MIGRATION_VERSION = "20260802_0015"
REQUIRED_TABLES = (
    "practice_sessions",
    "submissions",
    "execution_requests",
    "execution_payloads",
    "execution_outbox",
    "execution_public_results",
    "submission_evaluations",
    "learning_plans",
    "candidate_competency_evidence",
    "assessment_sessions",
    "simulation_sessions",
    "mock_interview_sessions",
    "ai_interactions",
    "readiness_snapshots",
    "recommendation_events",
    "role_readiness_profiles",
    "knowledge_sources",
    "knowledge_source_files",
    "knowledge_import_runs",
    "knowledge_problems",
    "knowledge_solutions",
    "knowledge_companies",
    "knowledge_topics",
    "knowledge_system_design_articles",
    "knowledge_candidate_problem_state",
    "knowledge_activity_events",
    "local_execution_queue",
    "local_execution_controller_status",
)
EXECUTION_ADAPTERS = {"LOCAL_FUNCTIONAL", "LOCAL_DOCKER", "KUBERNETES_JOB"}
AI_ADAPTERS = {"DETERMINISTIC", "OPENAI", "ANTHROPIC"}


def database_checks(engine: Engine) -> tuple[list[ReadinessCheck], int]:
    checks: list[ReadinessCheck] = []
    content_count = 0
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1")).scalar_one()
            checks.append(ReadinessCheck(name="postgresql", status="ready", detail="reachable"))
            version = connection.execute(
                text("SELECT version_num FROM alembic_version")
            ).scalar_one()
            checks.append(
                ReadinessCheck(
                    name="migration",
                    status="ready" if version == EXPECTED_MIGRATION_VERSION else "not_ready",
                    detail=f"database={version}; expected={EXPECTED_MIGRATION_VERSION}",
                )
            )
            missing = [
                table
                for table in REQUIRED_TABLES
                if connection.execute(
                    text("SELECT to_regclass(:table_name)"), {"table_name": table}
                ).scalar_one()
                is None
            ]
            checks.append(
                ReadinessCheck(
                    name="required_tables",
                    status="not_ready" if missing else "ready",
                    detail=(
                        f"missing={','.join(missing)}"
                        if missing
                        else "all required tables present"
                    ),
                )
            )
            content_count = int(
                connection.execute(
                    text(
                        """
                        SELECT
                          (SELECT count(*) FROM questions q
                           JOIN question_versions v ON v.id=q.current_published_version_id
                           WHERE v.state='published'::content_state)
                          + (SELECT count(*) FROM external_question_references)
                        """
                    )
                ).scalar_one()
            )
    except SQLAlchemyError as exc:
        checks.append(
            ReadinessCheck(
                name="postgresql",
                status="not_ready",
                detail=f"database check failed: {exc.__class__.__name__}",
            )
        )
    return checks, content_count


def local_execution_checks(engine: Engine, adapter: str) -> list[ReadinessCheck]:
    if adapter != "LOCAL_DOCKER":
        return []
    try:
        with engine.connect() as connection:
            row = (
                connection.execute(
                    text(
                        """
                        SELECT
                          heartbeat_at > CURRENT_TIMESTAMP - INTERVAL '30 seconds'
                            AS heartbeat_ready,
                          queue_depth,
                          python_runner_ready,
                          sql_runner_ready
                        FROM local_execution_controller_status
                        WHERE controller_key='local'
                        """
                    )
                )
                .mappings()
                .one_or_none()
            )
    except SQLAlchemyError as exc:
        return [
            ReadinessCheck(
                name="local_execution_controller",
                status="not_ready",
                detail=f"status check failed: {exc.__class__.__name__}",
            )
        ]
    if row is None:
        return [
            ReadinessCheck(
                name="local_execution_controller",
                status="not_ready",
                detail="controller heartbeat is unavailable",
            ),
            ReadinessCheck(
                name="python_runner",
                status="not_ready",
                detail="controller has not reported runner status",
            ),
            ReadinessCheck(
                name="sql_runner",
                status="not_ready",
                detail="controller has not reported runner status",
            ),
        ]

    controller_ready = row["heartbeat_ready"] is True
    python_ready = row["python_runner_ready"] is True
    sql_ready = row["sql_runner_ready"] is True
    return [
        ReadinessCheck(
            name="local_execution_controller",
            status="ready" if controller_ready else "not_ready",
            detail=(
                f"heartbeat fresh; queued={int(row['queue_depth'])}"
                if controller_ready
                else "controller heartbeat is stale"
            ),
        ),
        ReadinessCheck(
            name="python_runner",
            status="ready" if python_ready else "not_ready",
            detail="reachable through internal execution network" if python_ready else "unreachable",
        ),
        ReadinessCheck(
            name="sql_runner",
            status="ready" if sql_ready else "not_ready",
            detail="reachable through internal execution network" if sql_ready else "unreachable",
        ),
    ]


def valkey_check(url: str) -> ReadinessCheck:
    parsed = urlparse(url)
    host = parsed.hostname or "localhost"
    port = parsed.port or 6379
    try:
        with socket.create_connection((host, port), timeout=1.5) as connection:
            connection.sendall(b"*1\r\n$4\r\nPING\r\n")
            response = connection.recv(16)
        if response.startswith(b"+PONG"):
            return ReadinessCheck(name="valkey", status="ready", detail="reachable")
        return ReadinessCheck(name="valkey", status="not_ready", detail="unexpected response")
    except OSError as exc:
        return ReadinessCheck(
            name="valkey",
            status="not_ready",
            detail=f"connection failed: {exc.__class__.__name__}",
        )


def readiness_report(engine: Engine, settings: Settings) -> ReadinessResponse:
    checks, content_count = database_checks(engine)
    adapter = settings.execution_adapter.strip().upper()
    checks.extend(
        [
            valkey_check(settings.valkey_url),
            ReadinessCheck(
                name="content",
                status="ready" if content_count > 0 else "not_ready",
                detail=f"available records={content_count}",
            ),
            ReadinessCheck(
                name="execution_adapter",
                status="ready" if adapter in EXECUTION_ADAPTERS else "not_ready",
                detail=adapter,
            ),
            ReadinessCheck(
                name="async_execution_api",
                status="ready" if EXECUTION_ROUTES_REGISTERED else "not_ready",
                detail="registered" if EXECUTION_ROUTES_REGISTERED else "missing",
            ),
            ReadinessCheck(
                name="legacy_candidate_execution",
                status="ready" if LEGACY_SYNCHRONOUS_EXECUTION_BLOCKED else "not_ready",
                detail=(
                    "synchronous HTTP execution blocked"
                    if LEGACY_SYNCHRONOUS_EXECUTION_BLOCKED
                    else "unsafe synchronous route available"
                ),
            ),
            ReadinessCheck(
                name="ai_adapter",
                status="ready" if settings.ai_adapter in AI_ADAPTERS else "not_ready",
                detail=settings.ai_adapter,
            ),
        ]
    )
    checks.extend(local_execution_checks(engine, adapter))
    status = "ready" if all(check.status == "ready" for check in checks) else "not_ready"
    return ReadinessResponse(status=status, checks=checks)
