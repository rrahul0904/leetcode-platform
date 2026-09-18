"""Add candidate-owned AI Arena generations, scores, and public ratings.

Revision ID: 20260918_0021
Revises: 20260914_0020
Create Date: 2026-09-18
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260918_0021"
down_revision: str | None = "20260914_0020"
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
        "ai_arena_profiles",
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("rating", sa.Integer(), nullable=False, server_default="1000"),
        sa.Column("tier", sa.String(length=24), nullable=False, server_default="Bronze"),
        sa.Column("solved_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("submission_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.CheckConstraint("rating >= 0", name="ck_ai_arena_profiles_rating"),
        sa.CheckConstraint("solved_count >= 0", name="ck_ai_arena_profiles_solved"),
        sa.CheckConstraint("submission_count >= 0", name="ck_ai_arena_profiles_submissions"),
    )
    op.execute("ALTER TABLE ai_arena_profiles ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE ai_arena_profiles FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY ai_arena_profiles_select ON ai_arena_profiles
        FOR SELECT USING (true)
        """
    )
    op.execute(
        """
        CREATE POLICY ai_arena_profiles_insert ON ai_arena_profiles
        FOR INSERT WITH CHECK (
          user_id=NULLIF(current_setting('rigor.user_id', true), '')::uuid
          OR (session_user='rigor_migrator'
              AND current_setting('rigor.maintenance_bypass', true)='on')
        )
        """
    )
    op.execute(
        """
        CREATE POLICY ai_arena_profiles_update ON ai_arena_profiles
        FOR UPDATE
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

    op.create_table(
        "ai_arena_generations",
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
            "question_version_id",
            sa.Uuid(),
            sa.ForeignKey("question_versions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("generated_code", sa.Text(), nullable=False),
        sa.Column("provider", sa.String(length=80), nullable=False),
        sa.Column("model", sa.String(length=160), nullable=False),
        sa.Column("idempotency_key", sa.String(length=160), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.CheckConstraint(
            "char_length(btrim(prompt)) BETWEEN 1 AND 4000",
            name="ck_ai_arena_generations_prompt_length",
        ),
        sa.CheckConstraint(
            "char_length(generated_code) BETWEEN 1 AND 100000",
            name="ck_ai_arena_generations_code_length",
        ),
        sa.UniqueConstraint(
            "user_id",
            "idempotency_key",
            name="uq_ai_arena_generations_user_idempotency",
        ),
    )
    op.create_index(
        "ix_ai_arena_generations_user_question_created",
        "ai_arena_generations",
        ["user_id", "question_version_id", "created_at"],
    )
    owner_policy("ai_arena_generations")

    op.create_table(
        "ai_arena_results",
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
            "generation_id",
            sa.Uuid(),
            sa.ForeignKey("ai_arena_generations.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column(
            "submission_id",
            sa.Uuid(),
            sa.ForeignKey("submissions.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("correctness_score", sa.Integer(), nullable=False),
        sa.Column("performance_score", sa.Integer(), nullable=False),
        sa.Column("quality_score", sa.Integer(), nullable=False),
        sa.Column("efficiency_score", sa.Integer(), nullable=False),
        sa.Column("total_score", sa.Integer(), nullable=False),
        sa.Column("rating_delta", sa.Integer(), nullable=False),
        sa.Column("rating_after", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.CheckConstraint(
            "correctness_score BETWEEN 0 AND 70",
            name="ck_ai_arena_results_correctness",
        ),
        sa.CheckConstraint(
            "performance_score BETWEEN 0 AND 15",
            name="ck_ai_arena_results_performance",
        ),
        sa.CheckConstraint(
            "quality_score BETWEEN 0 AND 10",
            name="ck_ai_arena_results_quality",
        ),
        sa.CheckConstraint(
            "efficiency_score BETWEEN 0 AND 5",
            name="ck_ai_arena_results_efficiency",
        ),
        sa.CheckConstraint(
            "total_score BETWEEN 0 AND 100",
            name="ck_ai_arena_results_total",
        ),
        sa.CheckConstraint("rating_delta >= 0", name="ck_ai_arena_results_delta"),
        sa.CheckConstraint("rating_after >= 0", name="ck_ai_arena_results_rating"),
    )
    op.create_index(
        "ix_ai_arena_results_user_created",
        "ai_arena_results",
        ["user_id", "created_at"],
    )
    owner_policy("ai_arena_results")

    op.execute("GRANT SELECT, INSERT, UPDATE ON ai_arena_profiles TO rigor_app")
    op.execute("GRANT SELECT, INSERT ON ai_arena_generations TO rigor_app")
    op.execute("GRANT SELECT, INSERT ON ai_arena_results TO rigor_app")


def downgrade() -> None:
    op.drop_table("ai_arena_results")
    op.drop_table("ai_arena_generations")
    op.drop_table("ai_arena_profiles")
