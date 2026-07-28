"""Add candidate-owned progress for external practice references.

Revision ID: 20260721_0007
Revises: 20260721_0006
Create Date: 2026-07-21
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260721_0007"
down_revision: str | None = "20260721_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "external_reference_progress",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("organizations.id")),
        sa.Column(
            "candidate_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "external_reference_id",
            sa.Uuid(),
            sa.ForeignKey("external_question_references.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("status", sa.String(30), nullable=False, server_default="NOT_STARTED"),
        sa.Column("notes", sa.Text()),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
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
        sa.UniqueConstraint(
            "candidate_id", "external_reference_id", name="uq_external_reference_progress"
        ),
        sa.CheckConstraint(
            "status IN ('NOT_STARTED', 'IN_PROGRESS', 'COMPLETED')",
            name="ck_external_reference_progress_status",
        ),
    )
    op.create_index(
        "ix_external_progress_candidate_status",
        "external_reference_progress",
        ["candidate_id", "status", sa.text("updated_at DESC")],
    )
    op.execute("ALTER TABLE external_reference_progress ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE external_reference_progress FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY external_reference_progress_principal_isolation
        ON external_reference_progress
        USING (
          (session_user = 'rigor_migrator'
            AND current_setting('rigor.maintenance_bypass', true) = 'on')
          OR (
            candidate_id::text = NULLIF(current_setting('rigor.user_id', true), '')
            AND (
              organization_id IS NULL
              OR organization_id::text =
                   NULLIF(current_setting('rigor.organization_id', true), '')
            )
          )
        )
        WITH CHECK (
          (session_user = 'rigor_migrator'
            AND current_setting('rigor.maintenance_bypass', true) = 'on')
          OR (
            candidate_id::text = NULLIF(current_setting('rigor.user_id', true), '')
            AND (
              organization_id IS NULL
              OR organization_id::text =
                   NULLIF(current_setting('rigor.organization_id', true), '')
            )
          )
        )
        """
    )


def downgrade() -> None:
    op.execute(
        "DROP POLICY IF EXISTS external_reference_progress_principal_isolation "
        "ON external_reference_progress"
    )
    op.drop_index("ix_external_progress_candidate_status", table_name="external_reference_progress")
    op.drop_table("external_reference_progress")
