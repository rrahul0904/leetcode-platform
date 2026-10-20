from __future__ import annotations

import os
from typing import cast
from uuid import uuid4

import pytest
from rigor_api.config import Settings
from rigor_api.database import create_database_engine
from rigor_api.database_health import EXPECTED_MIGRATION_VERSION, readiness_report
from rigor_api.persistence import PlatformStatisticsRepository
from rigor_api.schemas import (
    ExecutionState,
    MockInterviewState,
    PracticeSessionState,
    ReadinessCheck,
    SimulationState,
)
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.engine import make_url


def test_hosted_kubernetes_adapter_is_not_ready_until_state_path_is_certified(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from rigor_api import database_health

    def fake_database_checks(_engine: Engine) -> tuple[list[ReadinessCheck], int]:
        return [], 1

    monkeypatch.setattr(database_health, "database_checks", fake_database_checks)
    settings = Settings(
        environment="production",
        execution_adapter="KUBERNETES_JOB",
        database_url="postgresql+psycopg://rigor:secret@db.internal:5432/rigor",
        operational_database_url="postgresql+psycopg://rigor:secret@db.internal:5432/rigor",
        valkey_url="rediss://cache.internal:6379/0",
        local_oidc_enabled=False,
        oidc_issuer="https://identity.example.com",
        oidc_jwks_url="https://identity.example.com/.well-known/jwks.json",
        s3_upload_bucket="rigor-private",
        sqs_execution_queue_url="https://sqs.us-east-1.amazonaws.com/123456789012/rigor-execution",
    )

    report = readiness_report(engine=cast(Engine, object()), settings=settings)
    checks = {check.name: check for check in report.checks}

    assert report.status == "not_ready"
    assert checks["execution_adapter"].status == "not_ready"
    assert "authoritative state path is certified" in checks["execution_adapter"].detail


def test_shared_lifecycle_values_are_stable() -> None:
    assert [state.value for state in PracticeSessionState] == [
        "CREATED",
        "IN_PROGRESS",
        "PAUSED",
        "SUBMITTED",
        "EVALUATING",
        "COMPLETED",
        "ABANDONED",
    ]
    assert [state.value for state in ExecutionState] == [
        "QUEUED",
        "RUNNING",
        "PASSED",
        "FAILED",
        "ERROR",
        "CANCELLED",
        "TIMED_OUT",
    ]
    assert len(SimulationState) == 8
    assert len(MockInterviewState) == 6


def test_postgresql_statistics_and_readiness_are_derived() -> None:
    settings = Settings()
    engine = create_database_engine(settings)
    try:
        statistics = PlatformStatisticsRepository(engine).statistics()
        assert statistics.hosted_questions >= statistics.published_hosted_questions
        assert statistics.external_references >= 0
        report = readiness_report(engine, settings)
        checks = {check.name: check for check in report.checks}
        assert checks["migration"].detail.startswith(f"database={EXPECTED_MIGRATION_VERSION}")
        assert checks["required_tables"].status == "ready"
        assert checks["content"].detail.startswith("published_questions=")
        assert {
            "postgresql",
            "valkey",
            "content",
            "execution_adapter",
            "ai_adapter",
        } <= checks.keys()
    finally:
        engine.dispose()


def test_runtime_role_is_forced_through_candidate_and_tenant_rls() -> None:
    migration_url_text = os.getenv("RIGOR_PLATFORM_TEST_DATABASE_URL")
    if migration_url_text is None:
        pytest.skip("set RIGOR_PLATFORM_TEST_DATABASE_URL to exercise PostgreSQL role isolation")
    migration_url = make_url(migration_url_text)
    runtime_url = migration_url.set(username="rigor_app", password="rigor_app_local_only")
    migrator = create_engine(
        migration_url,
        connect_args={"options": "-c rigor.maintenance_bypass=on"},
    )
    runtime = create_engine(runtime_url)
    organization_a, organization_b, candidate_a, candidate_b = (uuid4() for _ in range(4))
    suffix = uuid4().hex
    try:
        with migrator.begin() as connection:
            connection.execute(
                text("INSERT INTO organizations(id,name,slug) VALUES(:id,:name,:slug)"),
                {"id": organization_a, "name": "RLS A", "slug": f"rls-a-{suffix}"},
            )
            connection.execute(
                text("INSERT INTO organizations(id,name,slug) VALUES(:id,:name,:slug)"),
                {"id": organization_b, "name": "RLS B", "slug": f"rls-b-{suffix}"},
            )
            for candidate, label in ((candidate_a, "a"), (candidate_b, "b")):
                connection.execute(
                    text(
                        "INSERT INTO users(id,identity_subject,email,display_name) "
                        "VALUES(:id,:subject,:email,:name)"
                    ),
                    {
                        "id": candidate,
                        "subject": f"rls-{label}-{suffix}",
                        "email": f"rls-{label}-{suffix}@test.invalid",
                        "name": f"RLS {label}",
                    },
                )
        with runtime.begin() as connection:
            connection.execute(
                text("SELECT set_config('rigor.user_id',:value,true)"),
                {"value": str(candidate_a)},
            )
            connection.execute(
                text("SELECT set_config('rigor.organization_id',:value,true)"),
                {"value": str(organization_a)},
            )
            connection.execute(
                text(
                    "INSERT INTO practice_sessions(organization_id,candidate_id) "
                    "VALUES(:organization_id,:candidate_id)"
                ),
                {"organization_id": organization_a, "candidate_id": candidate_a},
            )
        with runtime.begin() as connection:
            connection.execute(
                text("SELECT set_config('rigor.user_id',:value,true)"),
                {"value": str(candidate_b)},
            )
            connection.execute(
                text("SELECT set_config('rigor.organization_id',:value,true)"),
                {"value": str(organization_b)},
            )
            assert (
                connection.execute(text("SELECT count(*) FROM practice_sessions")).scalar_one() == 0
            )
            connection.execute(text("SELECT set_config('rigor.maintenance_bypass','on',true)"))
            assert (
                connection.execute(text("SELECT count(*) FROM practice_sessions")).scalar_one() == 0
            )
            owner = connection.execute(
                text("SELECT tableowner FROM pg_tables WHERE tablename='practice_sessions'")
            ).scalar_one()
            assert owner != "rigor_app"
    finally:
        with migrator.begin() as connection:
            connection.execute(
                text("DELETE FROM practice_sessions WHERE candidate_id IN (:a,:b)"),
                {"a": candidate_a, "b": candidate_b},
            )
            connection.execute(
                text("DELETE FROM users WHERE id IN (:a,:b)"),
                {"a": candidate_a, "b": candidate_b},
            )
            connection.execute(
                text("DELETE FROM organizations WHERE id IN (:a,:b)"),
                {"a": organization_a, "b": organization_b},
            )
        runtime.dispose()
        migrator.dispose()
