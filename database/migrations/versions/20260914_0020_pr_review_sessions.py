"""Add candidate-owned PR review sessions and comments.

Revision ID: 20260914_0020
Revises: 20260911_0019
Create Date: 2026-09-14
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260914_0020"
down_revision: str | None = "20260911_0019"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def owner_policy(table: str) -> None:
    op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"""
        CREATE POLICY {table}_owner_isolation ON {table}
        USING (
          user_id=NULLIF(current_setting('rigor.user_id', true), '')::uuid
          OR (session_user='rigor_migrator'
              AND current_setting('rigor.maintenance_bypass', true)='on')
        )
        WITH CHECK (
          user_id=NULLIF(current_setting('rigor.user_id', true), '')::uuid
          OR (session_user='rigor_migrator'
              AND current_setting('rigor.maintenance_bypass', true)='on')
        )
        """
    )


def score_check(column: str) -> sa.CheckConstraint:
    return sa.CheckConstraint(
        f"{column} IS NULL OR ({column} >= 0 AND {column} <= 1)",
        name=f"ck_pr_review_sessions_{column}",
    )


def upgrade() -> None:
    op.create_table(
        "pr_review_sessions",
        sa.Column(
            "id",
            sa.Uuid(),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("challenge_id", sa.String(length=120), nullable=False),
        sa.Column(
            "status",
            sa.String(length=20),
            nullable=False,
            server_default="active",
        ),
        sa.Column("verdict", sa.String(length=30), nullable=True),
        sa.Column("score", sa.Integer(), nullable=True),
        sa.Column("recall", sa.Float(), nullable=True),
        sa.Column("precision", sa.Float(), nullable=True),
        sa.Column("severity_accuracy", sa.Float(), nullable=True),
        sa.Column("reasoning_quality", sa.Float(), nullable=True),
        sa.Column("verdict_correct", sa.Boolean(), nullable=True),
        sa.Column(
            "started_at",
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
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "char_length(btrim(challenge_id)) BETWEEN 1 AND 120",
            name="ck_pr_review_sessions_challenge_id_length",
        ),
        sa.CheckConstraint(
            "status IN ('active','submitted')",
            name="ck_pr_review_sessions_status",
        ),
        sa.CheckConstraint(
            "verdict IS NULL OR verdict IN "
            "('approve','comment','request-changes')",
            name="ck_pr_review_sessions_verdict",
        ),
        sa.CheckConstraint(
            "score IS NULL OR (score >= 0 AND score <= 100)",
            name="ck_pr_review_sessions_score",
        ),
        score_check("recall"),
        score_check("precision"),
        score_check("severity_accuracy"),
        score_check("reasoning_quality"),
    )
    op.create_index(
        "ix_pr_review_sessions_user_updated",
        "pr_review_sessions",
        ["user_id", "updated_at"],
    )
    op.create_index(
        "ix_pr_review_sessions_user_status_updated",
        "pr_review_sessions",
        ["user_id", "status", "updated_at"],
    )
    owner_policy("pr_review_sessions")

    op.create_table(
        "pr_review_comments",
        sa.Column(
            "id",
            sa.Uuid(),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "session_id",
            sa.Uuid(),
            sa.ForeignKey("pr_review_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("file_path", sa.String(length=500), nullable=False),
        sa.Column("line_number", sa.Integer(), nullable=False),
        sa.Column("severity", sa.String(length=20), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.CheckConstraint(
            "char_length(btrim(file_path)) BETWEEN 1 AND 500",
            name="ck_pr_review_comments_file_path_length",
        ),
        sa.CheckConstraint(
            "line_number > 0",
            name="ck_pr_review_comments_line_number",
        ),
        sa.CheckConstraint(
            "severity IN ('info','minor','major','blocker')",
            name="ck_pr_review_comments_severity",
        ),
        sa.CheckConstraint(
            "char_length(btrim(message)) BETWEEN 1 AND 4000",
            name="ck_pr_review_comments_message_length",
        ),
    )
    op.create_index(
        "ix_pr_review_comments_user_session_created",
        "pr_review_comments",
        ["user_id", "session_id", "created_at"],
    )
    owner_policy("pr_review_comments")

    op.execute(
        "GRANT SELECT, INSERT, UPDATE ON pr_review_sessions TO rigor_app"
    )
    op.execute(
        "GRANT SELECT, INSERT, DELETE ON pr_review_comments TO rigor_app"
    )


def downgrade() -> None:
    op.drop_table("pr_review_comments")
    op.drop_table("pr_review_sessions")
