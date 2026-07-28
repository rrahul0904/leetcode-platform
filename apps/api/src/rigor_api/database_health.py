from __future__ import annotations

import socket
from urllib.parse import urlparse

from sqlalchemy import Engine, text
from sqlalchemy.exc import SQLAlchemyError

from .config import Settings
from .schemas import ReadinessCheck, ReadinessResponse

EXPECTED_MIGRATION_VERSION = "20260721_0007"
REQUIRED_TABLES = (
    "practice_sessions",
    "submissions",
    "execution_requests",
    "learning_plans",
    "candidate_competency_evidence",
    "assessment_sessions",
    "simulation_sessions",
    "mock_interview_sessions",
    "ai_interactions",
    "readiness_snapshots",
    "recommendation_events",
)
EXECUTION_ADAPTERS = {"LOCAL_FUNCTIONAL", "KUBERNETES_JOB"}
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
                    detail=f"missing={','.join(missing)}"
                    if missing
                    else "all required tables present",
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
                status=(
                    "ready" if settings.execution_adapter in EXECUTION_ADAPTERS else "not_ready"
                ),
                detail=settings.execution_adapter,
            ),
            ReadinessCheck(
                name="ai_adapter",
                status="ready" if settings.ai_adapter in AI_ADAPTERS else "not_ready",
                detail=settings.ai_adapter,
            ),
        ]
    )
    status = "ready" if all(check.status == "ready" for check in checks) else "not_ready"
    return ReadinessResponse(status=status, checks=checks)
