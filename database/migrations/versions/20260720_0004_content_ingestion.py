"""Add universal content import, rights, duplicate, and generation records.

Revision ID: 20260720_0004
Revises: 20260720_0003
Create Date: 2026-07-20
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260720_0004"
down_revision: str | None = "20260720_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "questions",
        sa.Column("visibility", sa.String(20), nullable=False, server_default=sa.text("'public'")),
    )
    op.add_column(
        "questions",
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("organizations.id")),
    )
    op.create_check_constraint(
        "ck_questions_visibility", "questions", "visibility IN ('public', 'private')"
    )
    op.create_check_constraint(
        "ck_questions_private_tenant",
        "questions",
        "visibility = 'public' OR organization_id IS NOT NULL",
    )
    op.create_index(
        "ix_questions_tenant_visibility", "questions", ["organization_id", "visibility"]
    )

    op.create_table(
        "content_imports",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("importing_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("organizations.id")),
        sa.Column("source_filename", sa.String(500), nullable=False),
        sa.Column("source_method", sa.String(40), nullable=False),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("dry_run", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("question_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("accepted_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("rejected_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("warning_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_summary", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("rollback_available", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("rolled_back_at", sa.DateTime(timezone=True)),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint(
            "source_method IN ('git', 'json', 'jsonl', 'csv', 'zip', 'authoring', "
            "'generation', 'licensed_connector')",
            name="ck_content_imports_method",
        ),
        sa.CheckConstraint(
            "status IN ('processing', 'completed', 'completed_with_warnings', 'failed', "
            "'rolled_back')",
            name="ck_content_imports_status",
        ),
        sa.CheckConstraint(
            "question_count >= 0 AND accepted_count >= 0 AND rejected_count >= 0 "
            "AND warning_count >= 0",
            name="ck_content_imports_counts",
        ),
    )
    op.create_index("ix_content_imports_started", "content_imports", [sa.text("started_at DESC")])
    op.create_table(
        "content_import_items",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "import_id",
            sa.Uuid(),
            sa.ForeignKey("content_imports.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("source_path", sa.String(700), nullable=False),
        sa.Column("external_id", sa.String(24)),
        sa.Column("slug", sa.String(180)),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("normalized_hash", sa.String(64)),
        sa.Column("similarity_score", sa.Numeric(5, 4)),
        sa.Column("rights_action", sa.String(40)),
        sa.Column("errors", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("warnings", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("normalized_payload", postgresql.JSONB()),
        sa.Column("question_version_id", sa.Uuid(), sa.ForeignKey("question_versions.id")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.UniqueConstraint("import_id", "ordinal", name="uq_content_import_item_ordinal"),
        sa.CheckConstraint(
            "status IN ('accepted', 'rejected', 'warning', 'draft', 'rolled_back')",
            name="ck_content_import_items_status",
        ),
    )
    op.create_index(
        "ix_content_import_items_identity", "content_import_items", ["external_id", "slug"]
    )
    op.create_table(
        "content_import_stage_results",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "import_item_id",
            sa.Uuid(),
            sa.ForeignKey("content_import_items.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("stage", sa.String(80), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("findings", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("metrics", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "completed_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.UniqueConstraint("import_item_id", "stage", name="uq_import_item_stage"),
        sa.CheckConstraint(
            "status IN ('passed', 'warning', 'failed', 'skipped')",
            name="ck_import_stage_status",
        ),
    )
    op.create_table(
        "duplicate_candidates",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "import_item_id",
            sa.Uuid(),
            sa.ForeignKey("content_import_items.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("existing_question_version_id", sa.Uuid(), sa.ForeignKey("question_versions.id")),
        sa.Column("comparison_source", sa.String(200), nullable=False),
        sa.Column("dimension_scores", postgresql.JSONB(), nullable=False),
        sa.Column("similarity_score", sa.Numeric(5, 4), nullable=False),
        sa.Column("suggested_action", sa.String(50), nullable=False),
        sa.Column("manual_reviewer_flag", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("review_notes", sa.Text()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )
    op.create_table(
        "content_license_records",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "question_version_id",
            sa.Uuid(),
            sa.ForeignKey("question_versions.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("rights_basis", sa.String(40), nullable=False),
        sa.Column("license_identifier", sa.String(200), nullable=False),
        sa.Column("provider", sa.String(200)),
        sa.Column("agreement_identifier", sa.String(200)),
        sa.Column("certification", sa.Text(), nullable=False),
        sa.Column("evidence", postgresql.JSONB(), nullable=False),
        sa.Column("terms", postgresql.JSONB(), nullable=False),
        sa.Column("expiration_date", sa.Date()),
        sa.Column("created_by", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.CheckConstraint(
            "rights_basis IN ('original', 'organization_owned', 'licensed')",
            name="ck_license_rights_basis",
        ),
    )
    op.create_table(
        "generation_traces",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("import_item_id", sa.Uuid(), sa.ForeignKey("content_import_items.id")),
        sa.Column("manifest_id", sa.String(24), nullable=False),
        sa.Column("stage", sa.String(80), nullable=False),
        sa.Column("prompt_version", sa.String(80), nullable=False),
        sa.Column("model_provider", sa.String(120), nullable=False),
        sa.Column("model_identifier", sa.String(160), nullable=False),
        sa.Column("input_hash", sa.String(64), nullable=False),
        sa.Column("output_hash", sa.String(64), nullable=False),
        sa.Column("validation_results", postgresql.JSONB(), nullable=False),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("human_edits", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("reviewer_decisions", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("publication_version", sa.String(30)),
        sa.Column(
            "generated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.CheckConstraint("retry_count >= 0", name="ck_generation_trace_retries"),
    )

    op.execute("ALTER TABLE questions ENABLE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY questions_tenant_isolation ON questions
        USING (
            visibility = 'public'
            OR organization_id::text = NULLIF(current_setting('rigor.organization_id', true), '')
            OR current_setting('rigor.bypass_rls', true) = 'on'
        )
        WITH CHECK (
            visibility = 'public'
            OR organization_id::text = NULLIF(current_setting('rigor.organization_id', true), '')
            OR current_setting('rigor.bypass_rls', true) = 'on'
        )
        """
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS questions_tenant_isolation ON questions")
    op.execute("ALTER TABLE questions DISABLE ROW LEVEL SECURITY")
    op.drop_table("generation_traces")
    op.drop_table("content_license_records")
    op.drop_table("duplicate_candidates")
    op.drop_table("content_import_stage_results")
    op.drop_index("ix_content_import_items_identity", table_name="content_import_items")
    op.drop_table("content_import_items")
    op.drop_index("ix_content_imports_started", table_name="content_imports")
    op.drop_table("content_imports")
    op.drop_index("ix_questions_tenant_visibility", table_name="questions")
    op.drop_constraint("ck_questions_private_tenant", "questions", type_="check")
    op.drop_constraint("ck_questions_visibility", "questions", type_="check")
    op.drop_column("questions", "organization_id")
    op.drop_column("questions", "visibility")
