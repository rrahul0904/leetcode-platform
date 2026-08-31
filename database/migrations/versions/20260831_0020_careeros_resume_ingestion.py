"""Add CareerOS resume-file provenance and extraction metadata.

Revision ID: 20260831_0020
Revises: 20260830_0019
Create Date: 2026-08-31
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260831_0020"
down_revision: str | None = "20260830_0019"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "career_documents",
        sa.Column(
            "candidate_file_id",
            sa.Uuid(),
            sa.ForeignKey("candidate_files.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column(
        "career_documents",
        sa.Column(
            "extraction_method",
            sa.String(length=32),
            nullable=False,
            server_default=sa.text("'pasted'"),
        ),
    )
    op.add_column(
        "career_documents",
        sa.Column(
            "extraction_metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
    op.create_check_constraint(
        "ck_career_documents_extraction_method",
        "career_documents",
        "extraction_method IN ('pasted','pdf_text','docx_xml')",
    )
    op.create_index(
        "uq_career_documents_candidate_file",
        "career_documents",
        ["candidate_file_id"],
        unique=True,
        postgresql_where=sa.text("candidate_file_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_career_documents_candidate_file",
        table_name="career_documents",
    )
    op.drop_constraint(
        "ck_career_documents_extraction_method",
        "career_documents",
        type_="check",
    )
    op.drop_column("career_documents", "extraction_metadata")
    op.drop_column("career_documents", "extraction_method")
    op.drop_column("career_documents", "candidate_file_id")
