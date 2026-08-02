"""Add candidate knowledge-bank state and append-only activity.

Revision ID: 20260801_0013
Revises: 20260801_0012
Create Date: 2026-08-01
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260801_0013"
down_revision: str | None = "20260801_0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "knowledge_candidate_problem_state",
        sa.Column(
            "candidate_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "problem_id",
            sa.Uuid(),
            sa.ForeignKey("knowledge_problems.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("status", sa.String(30), nullable=False, server_default=sa.text("'viewed'")),
        sa.Column("bookmarked", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("revision_status", sa.String(30), nullable=False, server_default=sa.text("'none'")),
        sa.Column("private_notes", sa.Text(), nullable=False, server_default=sa.text("''")),
        sa.Column("view_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("solved_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("failed_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("total_seconds", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("last_language", sa.String(50)),
        sa.Column("first_viewed_at", sa.DateTime(timezone=True)),
        sa.Column("last_attempted_at", sa.DateTime(timezone=True)),
        sa.Column("solved_at", sa.DateTime(timezone=True)),
        sa.Column(
            "last_activity_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
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
            "status IN ('viewed', 'attempted', 'solved', 'failed')",
            name="ck_knowledge_candidate_problem_status",
        ),
        sa.CheckConstraint(
            "revision_status IN ('none', 'marked', 'due', 'completed')",
            name="ck_knowledge_candidate_revision_status",
        ),
        sa.CheckConstraint(
            "view_count >= 0 AND attempt_count >= 0 AND solved_count >= 0 "
            "AND failed_count >= 0 AND total_seconds >= 0",
            name="ck_knowledge_candidate_state_counts",
        ),
    )
    op.create_index(
        "ix_knowledge_candidate_state_recent",
        "knowledge_candidate_problem_state",
        ["candidate_id", "last_activity_at"],
    )
    op.create_index(
        "ix_knowledge_candidate_state_revision",
        "knowledge_candidate_problem_state",
        ["candidate_id", "revision_status", "last_activity_at"],
    )
    op.create_index(
        "ix_knowledge_candidate_state_bookmarks",
        "knowledge_candidate_problem_state",
        ["candidate_id", "bookmarked", "last_activity_at"],
    )

    op.create_table(
        "knowledge_activity_events",
        sa.Column(
            "id",
            sa.Uuid(),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "candidate_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "problem_id",
            sa.Uuid(),
            sa.ForeignKey("knowledge_problems.id", ondelete="CASCADE"),
        ),
        sa.Column("event_type", sa.String(60), nullable=False),
        sa.Column("language", sa.String(50)),
        sa.Column("duration_seconds", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column(
            "payload",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("idempotency_key", sa.String(180)),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.UniqueConstraint(
            "candidate_id",
            "idempotency_key",
            name="uq_knowledge_activity_idempotency",
        ),
        sa.CheckConstraint("duration_seconds >= 0", name="ck_knowledge_activity_duration"),
        sa.CheckConstraint(
            "event_type IN ('problem_viewed', 'session_started', 'draft_saved', "
            "'public_tests_run', 'submission_completed', 'problem_solved', "
            "'problem_failed', 'bookmark_changed', 'revision_changed', "
            "'notes_saved', 'session_time_recorded')",
            name="ck_knowledge_activity_type",
        ),
    )
    op.create_index(
        "ix_knowledge_activity_candidate_time",
        "knowledge_activity_events",
        ["candidate_id", "occurred_at"],
    )
    op.create_index(
        "ix_knowledge_activity_problem_time",
        "knowledge_activity_events",
        ["problem_id", "occurred_at"],
    )

    for table in ("knowledge_candidate_problem_state", "knowledge_activity_events"):
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")

    op.execute(
        """
        CREATE POLICY knowledge_candidate_state_owner
        ON knowledge_candidate_problem_state
        USING (
          candidate_id=NULLIF(current_setting('rigor.user_id', true), '')::uuid
          OR (session_user='rigor_migrator'
              AND current_setting('rigor.maintenance_bypass', true)='on')
        )
        WITH CHECK (
          candidate_id=NULLIF(current_setting('rigor.user_id', true), '')::uuid
          OR (session_user='rigor_migrator'
              AND current_setting('rigor.maintenance_bypass', true)='on')
        )
        """
    )
    op.execute(
        """
        CREATE POLICY knowledge_activity_owner
        ON knowledge_activity_events
        USING (
          candidate_id=NULLIF(current_setting('rigor.user_id', true), '')::uuid
          OR (session_user='rigor_migrator'
              AND current_setting('rigor.maintenance_bypass', true)='on')
        )
        WITH CHECK (
          candidate_id=NULLIF(current_setting('rigor.user_id', true), '')::uuid
          OR (session_user='rigor_migrator'
              AND current_setting('rigor.maintenance_bypass', true)='on')
        )
        """
    )

    op.execute(
        "GRANT SELECT, INSERT, UPDATE, DELETE ON knowledge_candidate_problem_state TO rigor_app"
    )
    op.execute("GRANT SELECT, INSERT ON knowledge_activity_events TO rigor_app")


def downgrade() -> None:
    op.drop_table("knowledge_activity_events")
    op.drop_table("knowledge_candidate_problem_state")
