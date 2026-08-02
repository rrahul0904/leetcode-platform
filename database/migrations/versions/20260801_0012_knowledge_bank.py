"""Add the imported coding and system-design knowledge bank.

Revision ID: 20260801_0012
Revises: 20260729_0011
Create Date: 2026-08-01
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260801_0012"
down_revision: str | None = "20260729_0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _timestamps() -> tuple[sa.Column, sa.Column]:
    return (
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
    )


def upgrade() -> None:
    op.create_table(
        "knowledge_sources",
        sa.Column(
            "id",
            sa.Uuid(),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("source_name", sa.String(300), nullable=False, unique=True),
        sa.Column("original_filename", sa.String(500)),
        sa.Column("archive_sha256", sa.String(64), unique=True),
        sa.Column("disposition", sa.String(60), nullable=False),
        sa.Column("license_identifier", sa.String(200)),
        sa.Column("attribution", sa.Text()),
        sa.Column(
            "source_metadata",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        *_timestamps(),
        sa.CheckConstraint(
            "disposition IN ('hostable_licensed', 'external_reference_only', "
            "'rights_review_required', 'rejected_proprietary')",
            name="ck_knowledge_sources_disposition",
        ),
    )

    op.create_table(
        "knowledge_import_runs",
        sa.Column(
            "id",
            sa.Uuid(),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "source_id",
            sa.Uuid(),
            sa.ForeignKey("knowledge_sources.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("corpus_sha256", sa.String(64), nullable=False),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("dry_run", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column(
            "counters",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "failures",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("source_id", "corpus_sha256", name="uq_knowledge_import_source_corpus"),
    )
    op.create_index(
        "ix_knowledge_import_runs_status_started",
        "knowledge_import_runs",
        ["status", "started_at"],
    )

    op.create_table(
        "knowledge_source_files",
        sa.Column(
            "id",
            sa.Uuid(),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "source_id",
            sa.Uuid(),
            sa.ForeignKey("knowledge_sources.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("relative_path", sa.Text(), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("byte_count", sa.BigInteger(), nullable=False),
        sa.Column("suffix", sa.String(30), nullable=False),
        sa.Column("classification", sa.String(40), nullable=False),
        sa.Column("parse_status", sa.String(30), nullable=False),
        sa.Column("parse_error", sa.Text()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.UniqueConstraint("source_id", "relative_path", "sha256", name="uq_knowledge_source_file"),
        sa.CheckConstraint("byte_count >= 0", name="ck_knowledge_source_file_bytes"),
    )
    op.create_index(
        "ix_knowledge_source_files_sha256",
        "knowledge_source_files",
        ["sha256"],
    )

    op.create_table(
        "knowledge_problems",
        sa.Column(
            "id",
            sa.Uuid(),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("canonical_key", sa.String(500), nullable=False, unique=True),
        sa.Column("external_id", sa.String(120)),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("slug", sa.String(500), nullable=False, unique=True),
        sa.Column("summary", sa.Text()),
        sa.Column("description", sa.Text()),
        sa.Column("input_format", sa.Text()),
        sa.Column("output_format", sa.Text()),
        sa.Column(
            "examples",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "constraints",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "hints",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("editorial", sa.Text()),
        sa.Column("difficulty", sa.String(30)),
        sa.Column("source_url", sa.Text()),
        sa.Column("popularity", sa.Float()),
        sa.Column("acceptance_rate", sa.Float()),
        sa.Column("publication_status", sa.String(40), nullable=False),
        sa.Column("review_status", sa.String(40), nullable=False),
        sa.Column("primary_language", sa.String(40)),
        sa.Column(
            "source_metadata",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "search_document",
            postgresql.TSVECTOR(),
            sa.Computed(
                "to_tsvector('english', coalesce(title, '') || ' ' || "
                "coalesce(description, '') || ' ' || coalesce(editorial, ''))",
                persisted=True,
            ),
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        *_timestamps(),
        sa.CheckConstraint(
            "difficulty IS NULL OR difficulty IN ('easy', 'medium', 'hard')",
            name="ck_knowledge_problem_difficulty",
        ),
        sa.CheckConstraint(
            "acceptance_rate IS NULL OR (acceptance_rate >= 0 AND acceptance_rate <= 100)",
            name="ck_knowledge_problem_acceptance",
        ),
    )
    op.create_index(
        "ix_knowledge_problems_search",
        "knowledge_problems",
        ["search_document"],
        postgresql_using="gin",
    )
    op.create_index(
        "ix_knowledge_problems_filters",
        "knowledge_problems",
        ["publication_status", "difficulty", "title"],
    )
    op.create_index(
        "ix_knowledge_problems_external_id",
        "knowledge_problems",
        ["external_id"],
    )

    op.create_table(
        "knowledge_problem_sources",
        sa.Column(
            "problem_id",
            sa.Uuid(),
            sa.ForeignKey("knowledge_problems.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "source_file_id",
            sa.Uuid(),
            sa.ForeignKey("knowledge_source_files.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("source_hash", sa.String(64), nullable=False),
        sa.Column("source_path", sa.Text(), nullable=False),
        sa.Column("disposition", sa.String(60), nullable=False),
        sa.Column(
            "observed_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )

    op.create_table(
        "knowledge_topics",
        sa.Column(
            "id",
            sa.Uuid(),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("slug", sa.String(160), nullable=False, unique=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("category", sa.String(80), nullable=False, server_default=sa.text("'topic'")),
        sa.Column("description", sa.Text()),
        *_timestamps(),
    )

    op.create_table(
        "knowledge_problem_topics",
        sa.Column(
            "problem_id",
            sa.Uuid(),
            sa.ForeignKey("knowledge_problems.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "topic_id",
            sa.Uuid(),
            sa.ForeignKey("knowledge_topics.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("confidence", sa.Float(), nullable=False, server_default=sa.text("1.0")),
        sa.Column("source", sa.String(80), nullable=False, server_default=sa.text("'imported'")),
        sa.CheckConstraint("confidence >= 0 AND confidence <= 1", name="ck_knowledge_topic_confidence"),
    )

    op.create_table(
        "knowledge_solution_approaches",
        sa.Column(
            "id",
            sa.Uuid(),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "problem_id",
            sa.Uuid(),
            sa.ForeignKey("knowledge_problems.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(300), nullable=False),
        sa.Column("slug", sa.String(300), nullable=False),
        sa.Column("explanation", sa.Text()),
        sa.Column("time_complexity", sa.String(200)),
        sa.Column("space_complexity", sa.String(200)),
        sa.Column("sequence_number", sa.Integer(), nullable=False, server_default=sa.text("1")),
        *_timestamps(),
        sa.UniqueConstraint("problem_id", "slug", name="uq_knowledge_problem_approach"),
        sa.CheckConstraint("sequence_number >= 1", name="ck_knowledge_approach_sequence"),
    )

    op.create_table(
        "knowledge_solutions",
        sa.Column(
            "id",
            sa.Uuid(),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "approach_id",
            sa.Uuid(),
            sa.ForeignKey("knowledge_solution_approaches.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "source_file_id",
            sa.Uuid(),
            sa.ForeignKey("knowledge_source_files.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("language", sa.String(50), nullable=False),
        sa.Column("runtime", sa.String(80)),
        sa.Column("source_code", sa.Text(), nullable=False),
        sa.Column("explanation", sa.Text()),
        sa.Column("source_hash", sa.String(64), nullable=False),
        sa.Column("is_executable", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("review_status", sa.String(40), nullable=False),
        *_timestamps(),
        sa.UniqueConstraint(
            "approach_id",
            "language",
            "source_hash",
            name="uq_knowledge_solution_variant",
        ),
    )
    op.create_index(
        "ix_knowledge_solutions_language",
        "knowledge_solutions",
        ["language", "review_status"],
    )

    op.create_table(
        "knowledge_companies",
        sa.Column(
            "id",
            sa.Uuid(),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("slug", sa.String(180), nullable=False, unique=True),
        sa.Column("name", sa.String(240), nullable=False, unique=True),
        sa.Column("overview", sa.Text()),
        *_timestamps(),
    )

    op.create_table(
        "knowledge_company_observations",
        sa.Column(
            "id",
            sa.Uuid(),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "problem_id",
            sa.Uuid(),
            sa.ForeignKey("knowledge_problems.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "company_id",
            sa.Uuid(),
            sa.ForeignKey("knowledge_companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "source_file_id",
            sa.Uuid(),
            sa.ForeignKey("knowledge_source_files.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("observation_window", sa.String(120)),
        sa.Column("frequency", sa.Float()),
        sa.Column("acceptance_rate", sa.Float()),
        sa.Column("difficulty", sa.String(30)),
        sa.Column("source_hash", sa.String(64), nullable=False),
        sa.Column(
            "observed_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.UniqueConstraint(
            "problem_id",
            "company_id",
            "observation_window",
            "source_hash",
            name="uq_knowledge_company_observation",
        ),
    )
    op.create_index(
        "ix_knowledge_company_problem_frequency",
        "knowledge_company_observations",
        ["company_id", "frequency", "problem_id"],
    )

    op.create_table(
        "knowledge_system_design_articles",
        sa.Column(
            "id",
            sa.Uuid(),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "source_file_id",
            sa.Uuid(),
            sa.ForeignKey("knowledge_source_files.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("slug", sa.String(500), nullable=False, unique=True),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column(
            "headings",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "image_paths",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("source_hash", sa.String(64), nullable=False),
        sa.Column("publication_status", sa.String(40), nullable=False),
        sa.Column("review_status", sa.String(40), nullable=False),
        sa.Column(
            "search_document",
            postgresql.TSVECTOR(),
            sa.Computed(
                "to_tsvector('english', coalesce(title, '') || ' ' || coalesce(body, ''))",
                persisted=True,
            ),
        ),
        *_timestamps(),
    )
    op.create_index(
        "ix_knowledge_system_design_search",
        "knowledge_system_design_articles",
        ["search_document"],
        postgresql_using="gin",
    )

    op.create_table(
        "knowledge_learning_resources",
        sa.Column(
            "id",
            sa.Uuid(),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "source_file_id",
            sa.Uuid(),
            sa.ForeignKey("knowledge_source_files.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("slug", sa.String(500), nullable=False, unique=True),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("category", sa.String(180), nullable=False),
        sa.Column("language", sa.String(50)),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("source_hash", sa.String(64), nullable=False),
        sa.Column("publication_status", sa.String(40), nullable=False),
        sa.Column("review_status", sa.String(40), nullable=False),
        *_timestamps(),
    )
    op.create_index(
        "ix_knowledge_resources_category_language",
        "knowledge_learning_resources",
        ["category", "language"],
    )

    # Candidate-facing APIs may read only publication-gated knowledge records.
    for table in (
        "knowledge_problems",
        "knowledge_topics",
        "knowledge_problem_topics",
        "knowledge_solution_approaches",
        "knowledge_solutions",
        "knowledge_companies",
        "knowledge_company_observations",
        "knowledge_system_design_articles",
        "knowledge_learning_resources",
    ):
        op.execute(f"GRANT SELECT ON {table} TO rigor_app")


def downgrade() -> None:
    for table in (
        "knowledge_learning_resources",
        "knowledge_system_design_articles",
        "knowledge_company_observations",
        "knowledge_companies",
        "knowledge_solutions",
        "knowledge_solution_approaches",
        "knowledge_problem_topics",
        "knowledge_topics",
        "knowledge_problem_sources",
        "knowledge_problems",
        "knowledge_source_files",
        "knowledge_import_runs",
        "knowledge_sources",
    ):
        op.drop_table(table)
