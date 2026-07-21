"""Add continuous source, reference, competency, family, and coverage models.

Revision ID: 20260720_0005
Revises: 20260720_0004
Create Date: 2026-07-20
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260720_0005"
down_revision: str | None = "20260720_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

COVERAGE_LEVELS = (
    "BLOCKED",
    "DISCOVERY_ONLY",
    "DEEPLINK_ONLY",
    "METADATA_ONLY",
    "ABSTRACT_SIGNAL_ONLY",
    "USER_PRIVATE_IMPORT",
    "OPEN_LICENSE_FULL_CONTENT",
    "PARTNER_LICENSED_FULL_CONTENT",
    "ENTERPRISE_OWNED_FULL_CONTENT",
    "PLATFORM_ORIGINAL_FULL_CONTENT",
)


def upgrade() -> None:
    op.add_column(
        "questions",
        sa.Column(
            "record_type",
            sa.String(50),
            nullable=False,
            server_default=sa.text("'platform_original_hosted_question'"),
        ),
    )
    op.add_column(
        "questions",
        sa.Column("owner_user_id", sa.Uuid(), sa.ForeignKey("users.id")),
    )
    op.create_check_constraint(
        "ck_questions_record_type",
        "questions",
        "record_type IN ("
        "'platform_original_hosted_question', 'licensed_hosted_question', "
        "'open_license_hosted_question', 'question_variation', 'practice_drill', "
        "'mock_interview_case', 'staff_principal_case_study', "
        "'user_private_question', 'enterprise_private_question')",
    )
    op.create_index("ix_questions_record_type", "questions", ["record_type", "visibility"])

    op.create_table(
        "source_registry",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("source_name", sa.String(240), nullable=False),
        sa.Column("canonical_domain", sa.String(255), nullable=False, unique=True),
        sa.Column("source_category", sa.String(80), nullable=False),
        sa.Column("discovery_method", sa.String(80), nullable=False),
        sa.Column(
            "discovered_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("last_reviewed_at", sa.DateTime(timezone=True)),
        sa.Column("reviewed_by", sa.Uuid(), sa.ForeignKey("users.id")),
        sa.Column("access_method", sa.String(80), nullable=False, server_default="manual_review"),
        sa.Column("rights_status", sa.String(60), nullable=False, server_default="unreviewed"),
        sa.Column("coverage_level", sa.String(60), nullable=False, server_default="DISCOVERY_ONLY"),
        sa.Column("collection_mode", sa.String(60), nullable=False, server_default="manual"),
        sa.Column("connector_status", sa.String(40), nullable=False, server_default="unreviewed"),
        sa.Column("estimated_content_volume", sa.BigInteger()),
        sa.Column("actual_indexed_volume", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("last_successful_sync", sa.DateTime(timezone=True)),
        sa.Column("next_scheduled_sync", sa.DateTime(timezone=True)),
        sa.Column("failure_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("priority", sa.SmallInteger(), nullable=False, server_default="50"),
        sa.Column("connector_type", sa.String(120)),
        sa.Column(
            "connector_configuration", postgresql.JSONB(), nullable=False, server_default="{}"
        ),
        sa.Column("pause_reason", sa.Text()),
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
            "rights_status IN ('unreviewed', 'blocked', 'metadata_permitted', "
            "'open_license_verified', 'partner_license_verified', "
            "'enterprise_owned_verified', 'platform_original')",
            name="ck_source_rights_status",
        ),
        sa.CheckConstraint(
            f"coverage_level IN ({', '.join(repr(value) for value in COVERAGE_LEVELS)})",
            name="ck_source_coverage_level",
        ),
        sa.CheckConstraint(
            "connector_status IN ('unreviewed', 'approved', 'paused', 'disabled', 'failing')",
            name="ck_source_connector_status",
        ),
        sa.CheckConstraint("priority BETWEEN 0 AND 100", name="ck_source_priority"),
        sa.CheckConstraint(
            "failure_count >= 0 AND actual_indexed_volume >= 0",
            name="ck_source_nonnegative_counts",
        ),
        sa.CheckConstraint(
            "connector_status <> 'approved' OR last_reviewed_at IS NOT NULL",
            name="ck_source_approval_requires_review",
        ),
        sa.CheckConstraint(
            "coverage_level NOT IN ('OPEN_LICENSE_FULL_CONTENT', "
            "'PARTNER_LICENSED_FULL_CONTENT', 'ENTERPRISE_OWNED_FULL_CONTENT') "
            "OR rights_status IN ('open_license_verified', 'partner_license_verified', "
            "'enterprise_owned_verified')",
            name="ck_source_full_content_requires_rights",
        ),
    )
    op.create_index(
        "ix_source_registry_status_priority",
        "source_registry",
        ["connector_status", sa.text("priority DESC")],
    )
    op.create_table(
        "source_sync_runs",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "source_id",
            sa.Uuid(),
            sa.ForeignKey("source_registry.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("sync_mode", sa.String(30), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("cursor_before", postgresql.JSONB()),
        sa.Column("cursor_after", postgresql.JSONB()),
        sa.Column("discovered_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("updated_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("deleted_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failure_message", sa.Text()),
        sa.Column("started_by", sa.Uuid(), sa.ForeignKey("users.id")),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint(
            "sync_mode IN ('initial_backfill', 'incremental', 'verification')",
            name="ck_source_sync_mode",
        ),
        sa.CheckConstraint(
            "status IN ('queued', 'running', 'completed', 'failed', 'cancelled')",
            name="ck_source_sync_status",
        ),
    )
    op.create_index(
        "ix_source_sync_runs_source_started",
        "source_sync_runs",
        ["source_id", sa.text("started_at DESC")],
    )
    op.create_table(
        "external_question_references",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("source_id", sa.Uuid(), sa.ForeignKey("source_registry.id"), nullable=False),
        sa.Column("source_external_id", sa.String(255)),
        sa.Column("canonical_url", sa.Text(), nullable=False),
        sa.Column("title", sa.String(500)),
        sa.Column("abstract", sa.Text()),
        sa.Column("difficulty", sa.String(40)),
        sa.Column("topic_metadata", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("source_metadata", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("source_content_hash", sa.String(64)),
        sa.Column("source_availability", sa.String(30), nullable=False, server_default="available"),
        sa.Column("access_tier", sa.String(30), nullable=False, server_default="public"),
        sa.Column("technology_freshness", sa.String(30), nullable=False, server_default="stable"),
        sa.Column(
            "first_seen_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "last_seen_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("last_verified_at", sa.DateTime(timezone=True)),
        sa.Column("last_content_change_at", sa.DateTime(timezone=True)),
        sa.Column("review_due_at", sa.DateTime(timezone=True)),
        sa.Column("related_hosted_question_id", sa.Uuid(), sa.ForeignKey("questions.id")),
        sa.Column(
            "search_document",
            postgresql.TSVECTOR(),
            sa.Computed(
                "to_tsvector('english', coalesce(title, '') || ' ' || coalesce(abstract, ''))",
                persisted=True,
            ),
        ),
        sa.UniqueConstraint("source_id", "canonical_url", name="uq_external_reference_url"),
        sa.CheckConstraint(
            "source_availability IN ('available', 'unavailable', 'deleted', 'unknown')",
            name="ck_external_reference_availability",
        ),
        sa.CheckConstraint(
            "access_tier IN ('public', 'account_required', 'premium', 'unknown')",
            name="ck_external_reference_access",
        ),
        sa.CheckConstraint(
            "technology_freshness IN ('stable', 'current', 'fast_moving', 'stale')",
            name="ck_external_reference_freshness",
        ),
    )
    op.create_index(
        "ix_external_reference_search",
        "external_question_references",
        ["search_document"],
        postgresql_using="gin",
    )
    op.create_index(
        "ix_external_reference_freshness",
        "external_question_references",
        ["source_availability", "review_due_at"],
    )
    op.create_table(
        "interview_intelligence_records",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("source_id", sa.Uuid(), sa.ForeignKey("source_registry.id")),
        sa.Column("signal_type", sa.String(80), nullable=False),
        sa.Column("normalized_summary", sa.Text(), nullable=False),
        sa.Column("company_style_slug", sa.String(100)),
        sa.Column("role_family", sa.String(100)),
        sa.Column("interview_stage", sa.String(100)),
        sa.Column("time_period_start", sa.Date()),
        sa.Column("time_period_end", sa.Date()),
        sa.Column("source_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("source_diversity", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("confidence", sa.Numeric(4, 3), nullable=False),
        sa.Column("contradictions", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("last_verified_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.CheckConstraint("confidence BETWEEN 0 AND 1", name="ck_intelligence_confidence"),
        sa.CheckConstraint(
            "source_count > 0 AND source_diversity > 0", name="ck_intelligence_sources"
        ),
    )
    op.create_table(
        "competencies",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("slug", sa.String(160), nullable=False, unique=True),
        sa.Column("name", sa.String(240), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("parent_competency_id", sa.Uuid(), sa.ForeignKey("competencies.id")),
        sa.Column("role_families", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("difficulty_min", sa.String(30), nullable=False, server_default="foundational"),
        sa.Column("difficulty_max", sa.String(30), nullable=False, server_default="principal"),
        sa.Column("coverage_score", sa.Numeric(5, 4), nullable=False, server_default="0"),
        sa.Column(
            "last_updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.CheckConstraint("coverage_score BETWEEN 0 AND 1", name="ck_competency_coverage"),
    )
    op.create_table(
        "competency_relationships",
        sa.Column(
            "source_competency_id",
            sa.Uuid(),
            sa.ForeignKey("competencies.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "target_competency_id",
            sa.Uuid(),
            sa.ForeignKey("competencies.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("relationship", sa.String(30), primary_key=True),
        sa.CheckConstraint(
            "relationship IN ('related', 'prerequisite')", name="ck_competency_relationship"
        ),
    )
    op.create_table(
        "question_competencies",
        sa.Column(
            "question_id",
            sa.Uuid(),
            sa.ForeignKey("questions.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("competency_id", sa.Uuid(), sa.ForeignKey("competencies.id"), primary_key=True),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("confidence", sa.Numeric(4, 3), nullable=False, server_default="1"),
        sa.CheckConstraint("confidence BETWEEN 0 AND 1", name="ck_question_competency_confidence"),
    )
    op.create_table(
        "external_reference_competencies",
        sa.Column(
            "external_reference_id",
            sa.Uuid(),
            sa.ForeignKey("external_question_references.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("competency_id", sa.Uuid(), sa.ForeignKey("competencies.id"), primary_key=True),
        sa.Column("confidence", sa.Numeric(4, 3), nullable=False),
        sa.CheckConstraint("confidence BETWEEN 0 AND 1", name="ck_reference_competency_confidence"),
    )
    op.create_table(
        "question_families",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("slug", sa.String(180), nullable=False, unique=True),
        sa.Column("name", sa.String(300), nullable=False),
        sa.Column("canonical_competency_id", sa.Uuid(), sa.ForeignKey("competencies.id")),
        sa.Column("core_problem_structure", sa.Text(), nullable=False),
        sa.Column("input_pattern", sa.Text(), nullable=False),
        sa.Column("output_pattern", sa.Text(), nullable=False),
        sa.Column("expected_complexity", sa.Text(), nullable=False),
        sa.Column("common_solution_patterns", postgresql.JSONB(), nullable=False),
        sa.Column("source_distribution", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("variation_dimensions", postgresql.JSONB(), nullable=False),
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
    op.create_table(
        "question_family_members",
        sa.Column(
            "family_id",
            sa.Uuid(),
            sa.ForeignKey("question_families.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("question_id", sa.Uuid(), sa.ForeignKey("questions.id"), primary_key=True),
        sa.Column("classification", sa.String(30), nullable=False),
        sa.Column("reasoning", sa.Text(), nullable=False),
        sa.Column("similarity_score", sa.Numeric(5, 4), nullable=False),
        sa.CheckConstraint(
            "classification IN ('EXACT_DUPLICATE', 'NEAR_DUPLICATE', 'SAME_FAMILY', "
            "'MEANINGFUL_VARIANT', 'UNRELATED', 'REVIEW_REQUIRED')",
            name="ck_family_member_classification",
        ),
    )
    op.create_table(
        "coverage_gap_briefs",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("competency_id", sa.Uuid(), sa.ForeignKey("competencies.id"), nullable=False),
        sa.Column("role_level", sa.String(30), nullable=False),
        sa.Column("difficulty", sa.String(30), nullable=False),
        sa.Column("hosted_count", sa.Integer(), nullable=False),
        sa.Column("external_reference_count", sa.Integer(), nullable=False),
        sa.Column("recommended_question_count", sa.Integer(), nullable=False),
        sa.Column("recommended_action", sa.Text(), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="open"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("resolved_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint(
            "hosted_count >= 0 AND external_reference_count >= 0 "
            "AND recommended_question_count > 0",
            name="ck_coverage_gap_counts",
        ),
        sa.CheckConstraint(
            "status IN ('open', 'brief_generated', 'in_progress', 'resolved', 'dismissed')",
            name="ck_coverage_gap_status",
        ),
    )


def downgrade() -> None:
    op.drop_table("coverage_gap_briefs")
    op.drop_table("question_family_members")
    op.drop_table("question_families")
    op.drop_table("external_reference_competencies")
    op.drop_table("question_competencies")
    op.drop_table("competency_relationships")
    op.drop_table("competencies")
    op.drop_table("interview_intelligence_records")
    op.drop_index("ix_external_reference_freshness", table_name="external_question_references")
    op.drop_index("ix_external_reference_search", table_name="external_question_references")
    op.drop_table("external_question_references")
    op.drop_index("ix_source_sync_runs_source_started", table_name="source_sync_runs")
    op.drop_table("source_sync_runs")
    op.drop_index("ix_source_registry_status_priority", table_name="source_registry")
    op.drop_table("source_registry")
    op.drop_index("ix_questions_record_type", table_name="questions")
    op.drop_constraint("ck_questions_record_type", "questions", type_="check")
    op.drop_column("questions", "owner_user_id")
    op.drop_column("questions", "record_type")
