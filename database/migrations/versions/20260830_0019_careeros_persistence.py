"""Add candidate-owned CareerOS documents, jobs, and analysis history.

Revision ID: 20260830_0019
Revises: 20260828_0018
Create Date: 2026-08-30
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260830_0019"
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
        "career_documents",
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
        sa.Column("kind", sa.Text(), nullable=False, server_default="resume"),
        sa.Column("title", sa.Text(), nullable=False, server_default="Resume"),
        sa.Column("raw_text", sa.Text(), nullable=False),
        sa.Column("content_sha256", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.CheckConstraint("kind IN ('resume')", name="ck_career_documents_kind"),
        sa.CheckConstraint(
            "char_length(btrim(raw_text)) BETWEEN 40 AND 100000",
            name="ck_career_documents_raw_text_length",
        ),
        sa.UniqueConstraint(
            "user_id",
            "kind",
            "content_sha256",
            name="uq_career_documents_user_kind_sha256",
        ),
    )
    op.create_index(
        "ix_career_documents_user_created",
        "career_documents",
        ["user_id", "created_at"],
    )
    owner_policy("career_documents")

    op.create_table(
        "career_jobs",
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
        sa.Column("job_title", sa.String(length=160), nullable=True),
        sa.Column("company", sa.String(length=160), nullable=True),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("job_description", sa.Text(), nullable=False),
        sa.Column("job_description_sha256", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="saved"),
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
        sa.Column("last_analyzed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('saved','tailored','applied','screen','interview','offer',"
            "'rejected','withdrawn')",
            name="ck_career_jobs_status",
        ),
        sa.CheckConstraint(
            "char_length(btrim(job_description)) BETWEEN 40 AND 100000",
            name="ck_career_jobs_description_length",
        ),
    )
    op.create_index(
        "ix_career_jobs_user_updated",
        "career_jobs",
        ["user_id", "updated_at"],
    )
    op.create_index(
        "ix_career_jobs_user_status",
        "career_jobs",
        ["user_id", "status"],
    )
    owner_policy("career_jobs")

    op.create_table(
        "career_job_analyses",
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
            "job_id",
            sa.Uuid(),
            sa.ForeignKey("career_jobs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "document_id",
            sa.Uuid(),
            sa.ForeignKey("career_documents.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("scoring_version", sa.String(length=32), nullable=False),
        sa.Column("fit_score", sa.Integer(), nullable=False),
        sa.Column("analysis", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.CheckConstraint("fit_score BETWEEN 0 AND 100", name="ck_career_analysis_fit_score"),
    )
    op.create_index(
        "ix_career_job_analyses_job_created",
        "career_job_analyses",
        ["job_id", "created_at"],
    )
    op.create_index(
        "ix_career_job_analyses_user_created",
        "career_job_analyses",
        ["user_id", "created_at"],
    )
    owner_policy("career_job_analyses")

    op.execute("GRANT SELECT, INSERT ON career_documents TO rigor_app")
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON career_jobs TO rigor_app")
    op.execute("GRANT SELECT, INSERT, DELETE ON career_job_analyses TO rigor_app")


def downgrade() -> None:
    op.drop_table("career_job_analyses")
    op.drop_table("career_jobs")
    op.drop_table("career_documents")
