"""Durable tenant-isolated employer code executions and transactional delivery.

Revision ID: 20261028_0026
Revises: 20261028_0025
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261028_0026"
down_revision: str | None = "20261028_0025"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "employer_code_executions",
        sa.Column("id", sa.Uuid(), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("candidate_id", sa.Uuid(), nullable=False),
        sa.Column("attempt_id", sa.Uuid(), nullable=False),
        sa.Column("assessment_version_id", sa.Uuid(), nullable=False),
        sa.Column("question_number", sa.SmallInteger(), nullable=False),
        sa.Column("language", sa.String(12), nullable=False),
        sa.Column("execution_mode", sa.String(12), nullable=False),
        sa.Column("status", sa.String(20), nullable=False,
                  server_default="queued"),
        sa.Column("idempotency_key", sa.String(160), nullable=False),
        sa.Column("request_sha256", sa.String(64), nullable=False),
        sa.Column("source_sha256", sa.String(64), nullable=False),
        sa.Column("source_code", sa.Text(), nullable=False),
        sa.Column("fixture_sha256", sa.String(64)),
        sa.Column("attempt_count", sa.SmallInteger(), nullable=False,
                  server_default="0"),
        sa.Column("lease_owner", sa.String(160)),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True)),
        sa.Column("job_namespace", sa.String(120)),
        sa.Column("job_name", sa.String(253)),
        sa.Column("runtime_ms", sa.Integer()),
        sa.Column("public_results", postgresql.JSONB()),
        sa.Column("hidden_total", sa.SmallInteger()),
        sa.Column("hidden_passed", sa.SmallInteger()),
        sa.Column("awarded_marks", sa.Integer()),
        sa.Column("error_category", sa.String(100)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("candidate_id", "idempotency_key",
                            name="uq_employer_code_execution_idempotency"),
        sa.CheckConstraint("question_number BETWEEN 1 AND 100",
                           name="ck_employer_code_question"),
        sa.CheckConstraint("language IN ('python','sql')",
                           name="ck_employer_code_language"),
        sa.CheckConstraint("execution_mode IN ('RUN','SUBMIT')",
                           name="ck_employer_code_mode"),
        sa.CheckConstraint(
            "status IN ('queued','dispatching','running','completed','failed','timeout')",
            name="ck_employer_code_state",
        ),
        sa.CheckConstraint("attempt_count BETWEEN 0 AND 10",
                           name="ck_employer_code_attempt_count"),
        sa.CheckConstraint("length(source_code) <= 100000",
                           name="ck_employer_code_source_limit"),
        sa.CheckConstraint(
            "request_sha256 ~ '^[0-9a-f]{64}$' AND source_sha256 ~ '^[0-9a-f]{64}$'",
            name="ck_employer_code_hashes",
        ),
        sa.ForeignKeyConstraint(
            ["attempt_id", "organization_id", "candidate_id"],
            ["employer_assessment_attempts.id", "employer_assessment_attempts.organization_id",
             "employer_assessment_attempts.candidate_id"],
            name="fk_employer_code_attempt_scope", ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["assessment_version_id", "organization_id"],
            ["employer_assessment_versions.id", "employer_assessment_versions.organization_id"],
            name="fk_employer_code_version_scope",
        ),
    )
    op.create_index(
        "ix_employer_code_reconcile", "employer_code_executions",
        ["status", "lease_expires_at", "created_at"],
    )
    op.create_index(
        "ix_employer_code_attempt", "employer_code_executions",
        ["attempt_id", "question_number", "created_at"],
    )

    op.create_table(
        "employer_code_execution_outbox",
        sa.Column("id", sa.Uuid(), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("execution_id", sa.Uuid(),
                  sa.ForeignKey("employer_code_executions.id", ondelete="CASCADE"),
                  nullable=False, unique=True),
        sa.Column("state", sa.String(12), nullable=False, server_default="pending"),
        sa.Column("attempt_count", sa.SmallInteger(), nullable=False,
                  server_default="0"),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("published_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("state IN ('pending','published')",
                           name="ck_employer_execution_outbox_state"),
    )
    op.create_index(
        "ix_employer_code_outbox", "employer_code_execution_outbox",
        ["state", "next_attempt_at"],
    )

    for table in ("employer_code_executions", "employer_code_execution_outbox"):
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")

    # API never gets UPDATE/DELETE on execution or outbox rows. Worker's
    # arbitrary-tenant SELECT is confined to its dedicated database role.
    op.execute("""
        CREATE POLICY employer_code_candidate_read ON employer_code_executions
        FOR SELECT TO rigor_app USING (
          candidate_id=NULLIF(current_setting('rigor.user_id', true), '')::uuid
          OR (
            organization_id=NULLIF(current_setting('rigor.organization_id', true), '')::uuid
            AND EXISTS (
              SELECT 1 FROM organization_memberships m
              JOIN employer_assessment_attempts a ON a.id=employer_code_executions.attempt_id
              WHERE m.organization_id=employer_code_executions.organization_id
                AND m.user_id=NULLIF(current_setting('rigor.user_id', true), '')::uuid
                AND m.status='active'
                AND m.role_slug IN ('owner','admin','reviewer','interviewer')
                AND a.status IN ('submitted','expired')
            )
          )
        )
    """)
    op.execute("""
        CREATE POLICY employer_code_candidate_insert ON employer_code_executions
        FOR INSERT TO rigor_app WITH CHECK (
          candidate_id=NULLIF(current_setting('rigor.user_id', true), '')::uuid
          AND EXISTS (
            SELECT 1 FROM employer_assessment_attempts a
            WHERE a.id=employer_code_executions.attempt_id
              AND a.candidate_id=employer_code_executions.candidate_id
              AND a.organization_id=employer_code_executions.organization_id
          )
        )
    """)
    op.execute("""
        CREATE POLICY employer_code_worker_access ON employer_code_executions
        FOR ALL TO rigor_execution_worker USING (true) WITH CHECK (true)
    """)
    op.execute("""
        CREATE POLICY employer_code_outbox_api_insert ON employer_code_execution_outbox
        FOR INSERT TO rigor_app WITH CHECK (
          EXISTS (SELECT 1 FROM employer_code_executions e
                  WHERE e.id=employer_code_execution_outbox.execution_id
                    AND e.candidate_id=NULLIF(current_setting('rigor.user_id',true),'')::uuid)
        )
    """)
    op.execute("""
        CREATE POLICY employer_code_outbox_worker_access ON employer_code_execution_outbox
        FOR ALL TO rigor_execution_worker USING (true) WITH CHECK (true)
    """)
    op.execute(
        "GRANT SELECT, INSERT ON employer_code_executions TO rigor_app"
    )
    op.execute("GRANT INSERT ON employer_code_execution_outbox TO rigor_app")
    op.execute(
        "GRANT SELECT, UPDATE ON employer_code_execution_outbox TO rigor_execution_worker"
    )
    op.execute(
        "GRANT SELECT, UPDATE ON employer_code_executions TO rigor_execution_worker"
    )
    for table in (
        "employer_assessment_versions",
        "employer_assessment_attempts",
        "employer_assessment_invitations",
        "employer_assessment_private_keys",
    ):
        op.execute(f"GRANT SELECT ON {table} TO rigor_execution_worker")
        op.execute(
            f"CREATE POLICY {table}_execution_worker_read ON {table} "
            "FOR SELECT TO rigor_execution_worker USING (true)"
        )


def downgrade() -> None:
    for table in (
        "employer_assessment_versions",
        "employer_assessment_attempts",
        "employer_assessment_invitations",
        "employer_assessment_private_keys",
    ):
        op.execute(
            f"DROP POLICY IF EXISTS {table}_execution_worker_read ON {table}"
        )
        op.execute(f"REVOKE SELECT ON {table} FROM rigor_execution_worker")
    op.drop_table("employer_code_execution_outbox")
    op.drop_index("ix_employer_code_attempt", table_name="employer_code_executions")
    op.drop_index("ix_employer_code_reconcile", table_name="employer_code_executions")
    op.drop_table("employer_code_executions")
