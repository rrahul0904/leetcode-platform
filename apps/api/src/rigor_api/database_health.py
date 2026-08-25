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

EXPECTED_MIGRATION_VERSION = "20260824_0016"
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
                        else f"count={len(REQUIRED_TABLES)}"
                    ),
                )
            )
            content_count = int(
                connection.execute(text("SELECT count(*) FROM question_versions")).scalar_one()
            )
    except SQLAlchemyError as exc:
        checks.append(
            ReadinessCheck(name="postgresql", status="not_ready", detail=type(exc).__name__)
        )
    return checks, content_count


def dependency_check(name: str, url: str) -> ReadinessCheck:
    parsed = urlparse(url)
    host = parsed.hostname
    port = parsed.port
    if not host or not port:
        return ReadinessCheck(name=name, status="not_ready", detail="invalid_url")
    try:
        with socket.create_connection((host, port), timeout=0.5):
            return ReadinessCheck(name=name, status="ready", detail=f"{host}:{port}")
    except OSError as exc:
        return ReadinessCheck(name=name, status="not_ready", detail=type(exc).__name__)


def readiness_report(engine: Engine, settings: Settings) -> ReadinessResponse:
    checks, content_count = database_checks(engine)
    checks.append(dependency_check("valkey", settings.valkey_url))
    checks.append(
        ReadinessCheck(
            name="content",
            status="ready" if content_count > 0 else "not_ready",
            detail=f"question_versions={content_count}",
        )
    )
    execution_adapter = settings.execution_adapter.upper()
    checks.append(
        ReadinessCheck(
            name="execution_adapter",
            status="ready" if execution_adapter in EXECUTION_ADAPTERS else "not_ready",
            detail=execution_adapter,
        )
    )
    ai_adapter = settings.ai_adapter.upper()
    checks.append(
        ReadinessCheck(
            name="ai_adapter",
            status="ready" if ai_adapter in AI_ADAPTERS else "not_ready",
            detail=ai_adapter,
        )
    )
    checks.append(
        ReadinessCheck(
            name="execution_routes",
            status=(
                "ready"
                if EXECUTION_ROUTES_REGISTERED and LEGACY_SYNCHRONOUS_EXECUTION_BLOCKED
                else "not_ready"
            ),
            detail=(
                "durable execution routes registered; legacy synchronous execution blocked"
                if EXECUTION_ROUTES_REGISTERED and LEGACY_SYNCHRONOUS_EXECUTION_BLOCKED
                else "execution route registration incomplete"
            ),
        )
    )
    return ReadinessResponse(
        status="ready" if all(check.status == "ready" for check in checks) else "not_ready",
        checks=checks,
    )
