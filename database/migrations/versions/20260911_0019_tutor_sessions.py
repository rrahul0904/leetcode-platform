"""Add candidate-owned adaptive tutor sessions and event log.

Revision ID: 20260911_0019
Revises: 20260828_0018
Create Date: 2026-09-11
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260911_0019"
down_revision: str | None = "20260828_0018"
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


def upgrade() -> None:
    op.create_table(
        "tutor_sessions",
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
            "question_id",
            sa.Uuid(),
            sa.ForeignKey("questions.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("mode", sa.String(length=20), nullable=False),
        sa.Column("surface", sa.String(length=20), nullable=False),
        sa.Column("candidate_level", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="active"),
        sa.Column("title", sa.String(length=240), nullable=True),
        sa.Column("provider", sa.String(length=80), nullable=True),
        sa.Column("model", sa.String(length=160), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
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
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "mode IN ('lesson','roadmap','practice','mock')",
            name="ck_tutor_sessions_mode",
        ),
        sa.CheckConstraint(
            "surface IN ('chat','code','whiteboard')",
            name="ck_tutor_sessions_surface",
        ),
        sa.CheckConstraint(
            "candidate_level IN ('junior','mid','senior','staff','manager')",
            name="ck_tutor_sessions_candidate_level",
        ),
        sa.CheckConstraint(
            "status IN ('active','ended')",
            name="ck_tutor_sessions_status",
        ),
        sa.CheckConstraint(
            "summary IS NULL OR char_length(summary) <= 20000",
            name="ck_tutor_sessions_summary_length",
        ),
    )
    op.create_index(
        "ix_tutor_sessions_user_started",
        "tutor_sessions",
        ["user_id", "started_at"],
    )
    op.create_index(
        "ix_tutor_sessions_user_status_updated",
        "tutor_sessions",
        ["user_id", "status", "updated_at"],
    )
    owner_policy("tutor_sessions")

    op.create_table(
        "tutor_events",
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
            sa.ForeignKey("tutor_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("event_type", sa.String(length=120), nullable=False),
        sa.Column("idempotency_key", sa.String(length=160), nullable=False),
        sa.Column(
            "payload",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.CheckConstraint(
            "char_length(btrim(event_type)) BETWEEN 1 AND 120",
            name="ck_tutor_events_event_type_length",
        ),
        sa.CheckConstraint(
            "char_length(btrim(idempotency_key)) BETWEEN 1 AND 160",
            name="ck_tutor_events_idempotency_key_length",
        ),
        sa.UniqueConstraint(
            "session_id",
            "idempotency_key",
            name="uq_tutor_events_session_idempotency",
        ),
    )
    op.create_index(
        "ix_tutor_events_user_session_created",
        "tutor_events",
        ["user_id", "session_id", "created_at"],
    )
    owner_policy("tutor_events")

    op.execute(
        "GRANT SELECT, INSERT, UPDATE ON tutor_sessions TO rigor_app"
    )
    op.execute(
        "GRANT SELECT, INSERT ON tutor_events TO rigor_app"
    )


def downgrade() -> None:
    op.drop_table("tutor_events")
    op.drop_table("tutor_sessions")
