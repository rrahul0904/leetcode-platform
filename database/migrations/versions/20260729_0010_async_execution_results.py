"""Add candidate-safe asynchronous execution result projection.

Revision ID: 20260729_0010
Revises: 20260728_0009
Create Date: 2026-07-29
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260729_0010"
down_revision: str | None = "20260728_0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "execution_public_results",
        sa.Column(
            "execution_request_id",
            sa.Uuid(),
            sa.ForeignKey("execution_requests.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "public_results",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "hidden_total",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "hidden_passed",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("stdout", sa.Text(), nullable=False, server_default=sa.text("''")),
        sa.Column("stderr", sa.Text(), nullable=False, server_default=sa.text("''")),
        sa.Column("candidate_message", sa.Text()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.CheckConstraint(
            "hidden_total >= 0 AND hidden_passed >= 0 AND hidden_passed <= hidden_total",
            name="ck_execution_public_results_hidden_counts",
        ),
    )

    op.execute("ALTER TABLE execution_public_results ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE execution_public_results FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY execution_public_results_principal_isolation
        ON execution_public_results
        USING (
          (session_user = 'rigor_migrator'
            AND current_setting('rigor.maintenance_bypass', true) = 'on')
          OR EXISTS (
            SELECT 1
            FROM execution_requests er
            WHERE er.id=execution_public_results.execution_request_id
          )
        )
        WITH CHECK (
          (session_user = 'rigor_migrator'
            AND current_setting('rigor.maintenance_bypass', true) = 'on')
          OR EXISTS (
            SELECT 1
            FROM execution_requests er
            WHERE er.id=execution_public_results.execution_request_id
          )
        )
        """
    )

    # Local development creates rigor_executor before migrations. Production may
    # bootstrap the equivalent role later through Secrets Manager/IaC, so grants
    # are conditional rather than making the schema migration depend on role order.
    op.execute(
        """
        DO $grant_executor$
        BEGIN
          IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'rigor_executor') THEN
            GRANT SELECT, INSERT, UPDATE, DELETE ON execution_requests TO rigor_executor;
            GRANT SELECT ON execution_payloads TO rigor_executor;
            GRANT SELECT, INSERT, UPDATE, DELETE ON execution_outbox TO rigor_executor;
            GRANT SELECT, INSERT, UPDATE, DELETE ON execution_public_results TO rigor_executor;
            GRANT SELECT ON question_versions TO rigor_executor;
            GRANT SELECT, INSERT ON execution_events TO rigor_executor;
            GRANT SELECT, UPDATE ON practice_sessions TO rigor_executor;
            GRANT SELECT, INSERT ON practice_session_events TO rigor_executor;
            GRANT SELECT, UPDATE ON submissions TO rigor_executor;
            GRANT SELECT, INSERT, UPDATE ON submission_results TO rigor_executor;
            GRANT SELECT, INSERT, UPDATE ON submission_evaluations TO rigor_executor;
          END IF;
        END
        $grant_executor$;
        """
    )


def downgrade() -> None:
    op.execute(
        "DROP POLICY IF EXISTS execution_public_results_principal_isolation "
        "ON execution_public_results"
    )
    op.drop_table("execution_public_results")
