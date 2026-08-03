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

EXPECTED_MIGRATION_VERSION = "20260803_0016"
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
                        f"missing={','.join(missing)}" if missing else "all required tables present"
                    ),
                )
            )
            content_count = int(
                connection.execute(
                    text(
                        """
                        SELECT
                          (SELECT count(*) FROM external_practice_references)
                          + (SELECT count(*) FROM question_versions)
                        """
                    )
                ).scalar_one()
            )
    except SQLAlchemyError as exc:
        checks.append(
            ReadinessCheck(
                name="postgresql",
                status="not_ready",
                detail=f"{exc.__class__.__name__}: database check failed",
            )
        )
    return checks, content_count


def _tcp_check(name: str, url: str) -> ReadinessCheck:
    parsed = urlparse(url)
    if parsed.hostname is None or parsed.port is None:
        return ReadinessCheck(name=name, status="not_ready", detail="invalid URL")
    try:
        with socket.create_connection((parsed.hostname, parsed.port), timeout=1.5):
            return ReadinessCheck(name=name, status="ready", detail="reachable")
    except OSError as exc:
        return ReadinessCheck(
            name=name,
            status="not_ready",
            detail=f"{exc.__class__.__name__}: unreachable",
        )


def readiness_report(engine: Engine, settings: Settings) -> ReadinessResponse:
    checks, content_count = database_checks(engine)
    checks.append(_tcp_check("valkey", settings.valkey_url))
    checks.append(
        ReadinessCheck(
            name="content",
            status="ready" if content_count > 0 else "not_ready",
            detail=f"available records={content_count}",
        )
    )
    checks.append(
        ReadinessCheck(
            name="execution_adapter",
            status=(
                "ready" if settings.execution_adapter in EXECUTION_ADAPTERS else "not_ready"
            ),
            detail=settings.execution_adapter,
        )
    )
    checks.append(
        ReadinessCheck(
            name="async_execution_api",
            status="ready" if EXECUTION_ROUTES_REGISTERED else "not_ready",
            detail="registered" if EXECUTION_ROUTES_REGISTERED else "missing",
        )
    )
    checks.append(
        ReadinessCheck(
            name="legacy_candidate_execution",
            status=("ready" if LEGACY_SYNCHRONOUS_EXECUTION_BLOCKED else "not_ready"),
            detail=(
                "synchronous HTTP execution blocked"
                if LEGACY_SYNCHRONOUS_EXECUTION_BLOCKED
                else "legacy synchronous execution still reachable"
            ),
        )
    )
    checks.append(
        ReadinessCheck(
            name="ai_adapter",
            status="ready" if settings.ai_adapter in AI_ADAPTERS else "not_ready",
            detail=settings.ai_adapter,
        )
    )
    return ReadinessResponse(
        status=("ready" if all(check.status == "ready" for check in checks) else "not_ready"),
        service="rigor-api",
        checks=checks,
    )
