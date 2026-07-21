"""Add the persisted candidate submission domain.

Revision ID: 20260720_0003
Revises: 20260720_0002
Create Date: 2026-07-20
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260720_0003"
down_revision: str | None = "20260720_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "submissions",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "candidate_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "question_version_id",
            sa.Uuid(),
            sa.ForeignKey("question_versions.id"),
            nullable=False,
        ),
        sa.Column("runtime", sa.String(60), nullable=False),
        sa.Column("submitted_source", sa.Text(), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="queued"),
        sa.Column("public_test_results", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("hidden_test_summary", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("error_category", sa.String(80)),
        sa.Column("execution_duration_ms", sa.Integer()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint(
            "status IN ('queued', 'running', 'passed', 'failed', 'error')",
            name="ck_submissions_status",
        ),
        sa.CheckConstraint(
            "runtime IN ('python3.13', 'postgresql18')",
            name="ck_submissions_runtime",
        ),
        sa.CheckConstraint(
            "char_length(submitted_source) BETWEEN 1 AND 100000",
            name="ck_submissions_source_length",
        ),
        sa.CheckConstraint(
            "execution_duration_ms IS NULL OR execution_duration_ms >= 0",
            name="ck_submissions_duration_nonnegative",
        ),
    )
    op.create_index(
        "ix_submissions_candidate_created",
        "submissions",
        ["candidate_id", sa.text("created_at DESC")],
    )
    op.create_index(
        "ix_submissions_question_candidate",
        "submissions",
        ["question_version_id", "candidate_id", "status"],
    )


def downgrade() -> None:
    op.drop_index("ix_submissions_question_candidate", table_name="submissions")
    op.drop_index("ix_submissions_candidate_created", table_name="submissions")
    op.drop_table("submissions")
