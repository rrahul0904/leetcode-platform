"""Add durable execution lifecycle, payloads, leases, and transactional outbox.

Revision ID: 20260728_0009
Revises: 20260728_0008
Create Date: 2026-07-28
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260728_0009"
down_revision: str | None = "20260728_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Keep legacy states because submission_results still uses the same enum.
    # New execution lifecycle code uses the canonical production states below.
    op.execute("ALTER TYPE execution_state ADD VALUE IF NOT EXISTS 'DISPATCHING'")
    op.execute("ALTER TYPE execution_state ADD VALUE IF NOT EXISTS 'COMPLETED'")
    op.execute("ALTER TYPE execution_state ADD VALUE IF NOT EXISTS 'TIMEOUT'")

    op.add_column(
        "execution_requests",
        sa.Column(
            "execution_type",
            sa.String(20),
            nullable=False,
            server_default=sa.text("'RUN'"),
        ),
    )
    op.add_column(
        "execution_requests",
        sa.Column(
            "language",
            sa.String(30),
            nullable=False,
            server_default=sa.text("'python'"),
        ),
    )
    op.add_column("execution_requests", sa.Column("code_reference", sa.String(500)))
    op.add_column("execution_requests", sa.Column("input_reference", sa.String(500)))
    op.add_column(
        "execution_requests",
        sa.Column(
            "request_hash",
            sa.String(64),
            nullable=False,
            server_default=sa.text("repeat('0', 64)"),
        ),
    )
    op.add_column("execution_requests", sa.Column("dispatch_started_at", sa.DateTime(timezone=True)))
    op.add_column("execution_requests", sa.Column("running_at", sa.DateTime(timezone=True)))
    op.add_column(
        "execution_requests",
        sa.Column(
            "attempt_count",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )
    op.add_column("execution_requests", sa.Column("lease_owner", sa.String(160)))
    op.add_column("execution_requests", sa.Column("lease_expires_at", sa.DateTime(timezone=True)))
    op.add_column("execution_requests", sa.Column("runtime_ms", sa.Integer()))
    op.add_column("execution_requests", sa.Column("cpu_ms", sa.Integer()))
    op.add_column("execution_requests", sa.Column("memory_peak_bytes", sa.BigInteger()))
    op.add_column("execution_requests", sa.Column("exit_code", sa.Integer()))
    op.add_column("execution_requests", sa.Column("result_reference", sa.String(500)))
    op.add_column("execution_requests", sa.Column("error_category", sa.String(100)))
    op.add_column(
        "execution_requests",
        sa.Column(
            "trace_id",
            sa.String(160),
            nullable=False,
            server_default=sa.text("'legacy'"),
        ),
    )
    op.add_column("execution_requests", sa.Column("kubernetes_namespace", sa.String(120)))
    op.add_column("execution_requests", sa.Column("kubernetes_job_name", sa.String(253)))

    # Historical request rows predate scoped request fingerprints.
    op.execute(
        """
        UPDATE execution_requests
        SET request_hash=source_hash
        WHERE request_hash=repeat('0', 64)
        """
    )

    op.create_check_constraint(
        "ck_execution_attempt_count",
        "execution_requests",
        "attempt_count >= 0",
    )
    op.create_check_constraint(
        "ck_execution_runtime_metrics",
        "execution_requests",
        "(runtime_ms IS NULL OR runtime_ms >= 0) "
        "AND (cpu_ms IS NULL OR cpu_ms >= 0) "
        "AND (memory_peak_bytes IS NULL OR memory_peak_bytes >= 0)",
    )
    op.create_index(
        "ix_execution_requests_lease_reconciliation",
        "execution_requests",
        ["state", "lease_expires_at"],
    )
    op.create_index(
        "ix_execution_requests_kubernetes_job",
        "execution_requests",
        ["kubernetes_namespace", "kubernetes_job_name"],
        unique=True,
        postgresql_where=sa.text("kubernetes_job_name IS NOT NULL"),
    )

    op.create_table(
        "execution_payloads",
        sa.Column(
            "execution_request_id",
            sa.Uuid(),
            sa.ForeignKey("execution_requests.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("source_code", sa.Text(), nullable=False),
        sa.Column(
            "input_payload",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )

    op.create_table(
        "execution_outbox",
        sa.Column(
            "id",
            sa.Uuid(),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("aggregate_type", sa.String(80), nullable=False),
        sa.Column("aggregate_id", sa.Uuid(), nullable=False),
        sa.Column("event_type", sa.String(120), nullable=False),
        sa.Column("dedupe_key", sa.String(240), nullable=False, unique=True),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("published_at", sa.DateTime(timezone=True)),
        sa.Column(
            "attempt_count",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "next_attempt_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("last_error", sa.Text()),
        sa.CheckConstraint("attempt_count >= 0", name="ck_execution_outbox_attempt_count"),
    )
    op.create_index(
        "ix_execution_outbox_pending",
        "execution_outbox",
        ["next_attempt_at", "created_at"],
        postgresql_where=sa.text("published_at IS NULL"),
    )
    op.create_index(
        "ix_execution_outbox_aggregate",
        "execution_outbox",
        ["aggregate_type", "aggregate_id", "created_at"],
    )

    for table in ("execution_payloads", "execution_outbox"):
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")

    op.execute(
        """
        CREATE POLICY execution_payloads_principal_isolation
        ON execution_payloads
        USING (
          (session_user = 'rigor_migrator'
            AND current_setting('rigor.maintenance_bypass', true) = 'on')
          OR EXISTS (
            SELECT 1
            FROM execution_requests er
            WHERE er.id=execution_payloads.execution_request_id
          )
        )
        WITH CHECK (
          (session_user = 'rigor_migrator'
            AND current_setting('rigor.maintenance_bypass', true) = 'on')
          OR EXISTS (
            SELECT 1
            FROM execution_requests er
            WHERE er.id=execution_payloads.execution_request_id
          )
        )
        """
    )
    op.execute(
        """
        CREATE POLICY execution_outbox_principal_isolation
        ON execution_outbox
        USING (
          (session_user = 'rigor_migrator'
            AND current_setting('rigor.maintenance_bypass', true) = 'on')
          OR EXISTS (
            SELECT 1
            FROM execution_requests er
            WHERE er.id=execution_outbox.aggregate_id
              AND execution_outbox.aggregate_type='execution'
          )
        )
        WITH CHECK (
          (session_user = 'rigor_migrator'
            AND current_setting('rigor.maintenance_bypass', true) = 'on')
          OR EXISTS (
            SELECT 1
            FROM execution_requests er
            WHERE er.id=execution_outbox.aggregate_id
              AND execution_outbox.aggregate_type='execution'
          )
        )
        """
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS execution_outbox_principal_isolation ON execution_outbox")
    op.execute("DROP POLICY IF EXISTS execution_payloads_principal_isolation ON execution_payloads")
    op.drop_table("execution_outbox")
    op.drop_table("execution_payloads")

    op.drop_index("ix_execution_requests_kubernetes_job", table_name="execution_requests")
    op.drop_index("ix_execution_requests_lease_reconciliation", table_name="execution_requests")
    op.drop_constraint("ck_execution_runtime_metrics", "execution_requests", type_="check")
    op.drop_constraint("ck_execution_attempt_count", "execution_requests", type_="check")

    for column in (
        "kubernetes_job_name",
        "kubernetes_namespace",
        "trace_id",
        "error_category",
        "result_reference",
        "exit_code",
        "memory_peak_bytes",
        "cpu_ms",
        "runtime_ms",
        "lease_expires_at",
        "lease_owner",
        "attempt_count",
        "running_at",
        "dispatch_started_at",
        "request_hash",
        "input_reference",
        "code_reference",
        "language",
        "execution_type",
    ):
        op.drop_column("execution_requests", column)

    # PostgreSQL enum values are intentionally retained. Removing enum labels in a
    # downgrade requires rebuilding every dependent column and is riskier than
    # retaining unused forward-compatible labels.
