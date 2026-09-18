"""Add candidate-owned question bookmarks and notes.

Revision ID: 20260828_0018
Revises: 20260826_0017
Create Date: 2026-08-28
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260828_0018"
down_revision: str | None = "20260826_0017"
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
        "candidate_question_bookmarks",
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "question_id",
            sa.Uuid(),
            sa.ForeignKey("questions.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )
    op.create_index(
        "ix_candidate_question_bookmarks_user_created",
        "candidate_question_bookmarks",
        ["user_id", "created_at"],
    )
    owner_policy("candidate_question_bookmarks")

    op.create_table(
        "candidate_question_notes",
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
            sa.ForeignKey("questions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("body", sa.Text(), nullable=False),
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
            "char_length(btrim(body)) BETWEEN 1 AND 10000",
            name="ck_candidate_question_notes_body_length",
        ),
    )
    op.create_index(
        "ix_candidate_question_notes_user_question_updated",
        "candidate_question_notes",
        ["user_id", "question_id", "updated_at"],
    )
    owner_policy("candidate_question_notes")

    op.execute(
        "GRANT SELECT, INSERT, DELETE ON candidate_question_bookmarks TO rigor_app"
    )
    op.execute(
        "GRANT SELECT, INSERT, UPDATE, DELETE ON candidate_question_notes TO rigor_app"
    )


def downgrade() -> None:
    op.drop_table("candidate_question_notes")
    op.drop_table("candidate_question_bookmarks")
