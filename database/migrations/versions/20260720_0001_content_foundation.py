"""Create identity and normalized content foundation.

Revision ID: 20260720_0001
Revises: None
Create Date: 2026-07-20
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

revision: str = "20260720_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

content_state = postgresql.ENUM(
    "draft",
    "generated",
    "automated_validation_failed",
    "awaiting_technical_review",
    "awaiting_editorial_review",
    "approved",
    "published",
    "deprecated",
    "archived",
    name="content_state",
    create_type=False,
)
review_kind = postgresql.ENUM(
    "technical", "editorial", name="review_kind", create_type=False
)
review_outcome = postgresql.ENUM(
    "approved",
    "changes_requested",
    "rejected",
    name="review_outcome",
    create_type=False,
)


def timestamps() -> tuple[sa.Column[sa.DateTime], sa.Column[sa.DateTime]]:
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
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    content_state.create(op.get_bind())
    review_kind.create(op.get_bind())
    review_outcome.create(op.get_bind())

    op.create_table(
        "organizations",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("slug", sa.String(100), nullable=False, unique=True),
        *timestamps(),
    )
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("identity_subject", sa.String(255), nullable=False, unique=True),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("display_name", sa.String(160), nullable=False),
        sa.Column("email_verified", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        *timestamps(),
    )
    op.create_index(
        "uq_users_active_email",
        "users",
        [sa.text("lower(email)")],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_table(
        "organization_memberships",
        sa.Column(
            "organization_id", sa.Uuid(), sa.ForeignKey("organizations.id"), primary_key=True
        ),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("role_slug", sa.String(80), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )
    op.create_table(
        "consent_records",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("purpose", sa.String(100), nullable=False),
        sa.Column("provider", sa.String(100)),
        sa.Column("granted", sa.Boolean(), nullable=False),
        sa.Column("policy_version", sa.String(40), nullable=False),
        sa.Column(
            "recorded_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )

    op.create_table(
        "question_tracks",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("slug", sa.String(80), nullable=False, unique=True),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("target_count", sa.Integer(), nullable=False),
        sa.CheckConstraint("target_count > 0", name="ck_question_tracks_target_positive"),
    )
    op.create_table(
        "skills",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("slug", sa.String(100), nullable=False, unique=True),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("category", sa.String(100), nullable=False),
    )
    op.create_table(
        "company_style_tags",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("slug", sa.String(100), nullable=False, unique=True),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("independence_disclaimer", sa.Text(), nullable=False),
    )
    op.create_table(
        "questions",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("external_id", sa.String(24), nullable=False, unique=True),
        sa.Column("slug", sa.String(180), nullable=False, unique=True),
        sa.Column(
            "primary_track_id", sa.Uuid(), sa.ForeignKey("question_tracks.id"), nullable=False
        ),
        sa.Column("current_published_version_id", sa.Uuid()),
        sa.Column("archived_at", sa.DateTime(timezone=True)),
        *timestamps(),
    )
    op.create_table(
        "question_versions",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("question_id", sa.Uuid(), sa.ForeignKey("questions.id"), nullable=False),
        sa.Column("version", sa.String(30), nullable=False),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("problem_statement", sa.Text(), nullable=False),
        sa.Column("expected_seniority", sa.String(24), nullable=False),
        sa.Column("difficulty", sa.String(24), nullable=False),
        sa.Column("conceptual_difficulty", sa.SmallInteger(), nullable=False),
        sa.Column("implementation_difficulty", sa.SmallInteger(), nullable=False),
        sa.Column("scale", sa.SmallInteger(), nullable=False),
        sa.Column("ambiguity", sa.SmallInteger(), nullable=False),
        sa.Column("prerequisite_depth", sa.SmallInteger(), nullable=False),
        sa.Column("duration_minutes", sa.SmallInteger(), nullable=False),
        sa.Column("state", content_state, nullable=False, server_default="draft"),
        sa.Column("structured_content", postgresql.JSONB(), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("source_revision", sa.String(64), nullable=False),
        sa.Column(
            "search_document",
            postgresql.TSVECTOR(),
            sa.Computed(
                "to_tsvector('english', coalesce(title, '') || ' ' || "
                "coalesce(problem_statement, ''))",
                persisted=True,
            ),
        ),
        *timestamps(),
        sa.UniqueConstraint("question_id", "version", name="uq_question_versions_version"),
        sa.CheckConstraint(
            "conceptual_difficulty BETWEEN 1 AND 5 AND implementation_difficulty BETWEEN 1 AND 5 "
            "AND scale BETWEEN 1 AND 5 AND ambiguity BETWEEN 1 AND 5 "
            "AND prerequisite_depth BETWEEN 1 AND 5",
            name="ck_question_versions_dimensions",
        ),
        sa.CheckConstraint(
            "duration_minutes BETWEEN 15 AND 240", name="ck_question_versions_duration"
        ),
    )
    op.create_foreign_key(
        "fk_questions_published_version",
        "questions",
        "question_versions",
        ["current_published_version_id"],
        ["id"],
        use_alter=True,
    )
    op.create_index(
        "ix_question_versions_search",
        "question_versions",
        ["search_document"],
        postgresql_using="gin",
    )
    op.create_index("ix_question_versions_state", "question_versions", ["state", "updated_at"])
    op.create_table(
        "question_skills",
        sa.Column(
            "question_version_id",
            sa.Uuid(),
            sa.ForeignKey("question_versions.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("skill_id", sa.Uuid(), sa.ForeignKey("skills.id"), primary_key=True),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_table(
        "question_company_tags",
        sa.Column(
            "question_version_id",
            sa.Uuid(),
            sa.ForeignKey("question_versions.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "company_style_tag_id",
            sa.Uuid(),
            sa.ForeignKey("company_style_tags.id"),
            primary_key=True,
        ),
        sa.Column("relevance_rationale", sa.Text(), nullable=False),
        sa.Column("public_theme_sources", postgresql.JSONB(), nullable=False, server_default="[]"),
    )
    op.create_table(
        "learning_objectives",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "question_version_id",
            sa.Uuid(),
            sa.ForeignKey("question_versions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("ordinal", sa.SmallInteger(), nullable=False),
        sa.Column("objective", sa.Text(), nullable=False),
        sa.UniqueConstraint("question_version_id", "ordinal", name="uq_learning_objective_ordinal"),
    )
    op.create_table(
        "question_prerequisites",
        sa.Column(
            "question_version_id",
            sa.Uuid(),
            sa.ForeignKey("question_versions.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "prerequisite_question_id", sa.Uuid(), sa.ForeignKey("questions.id"), primary_key=True
        ),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.CheckConstraint("question_version_id IS NOT NULL", name="ck_prerequisite_nonnull"),
    )
    op.create_table(
        "solutions",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "question_version_id",
            sa.Uuid(),
            sa.ForeignKey("question_versions.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("reference_solution", sa.Text(), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column("trade_off_analysis", postgresql.JSONB(), nullable=False),
        sa.Column("source_content_hash", sa.String(64), nullable=False),
        *timestamps(),
    )
    op.create_table(
        "rubrics",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "question_version_id",
            sa.Uuid(),
            sa.ForeignKey("question_versions.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("score_bands", postgresql.JSONB(), nullable=False),
        *timestamps(),
    )
    op.create_table(
        "rubric_dimensions",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "rubric_id", sa.Uuid(), sa.ForeignKey("rubrics.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("weight", sa.SmallInteger(), nullable=False),
        sa.Column("ordinal", sa.SmallInteger(), nullable=False),
        sa.Column("indicators", postgresql.JSONB(), nullable=False),
        sa.CheckConstraint("weight BETWEEN 1 AND 100", name="ck_rubric_dimensions_weight"),
        sa.UniqueConstraint("rubric_id", "ordinal", name="uq_rubric_dimension_ordinal"),
    )
    op.create_table(
        "validation_runs",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "question_version_id",
            sa.Uuid(),
            sa.ForeignKey("question_versions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("validator_version", sa.String(60), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("findings", postgresql.JSONB(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
    )
    op.create_table(
        "review_assignments",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "question_version_id",
            sa.Uuid(),
            sa.ForeignKey("question_versions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("reviewer_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("kind", review_kind, nullable=False),
        sa.Column(
            "assigned_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("question_version_id", "kind", name="uq_review_assignment_kind"),
    )
    op.create_table(
        "review_decisions",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "review_assignment_id",
            sa.Uuid(),
            sa.ForeignKey("review_assignments.id"),
            nullable=False,
        ),
        sa.Column("reviewer_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("outcome", review_outcome, nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )
    op.create_table(
        "provenance_records",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "question_version_id",
            sa.Uuid(),
            sa.ForeignKey("question_versions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("author_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("originality_statement", sa.Text(), nullable=False),
        sa.Column("authoring_method", sa.Text(), nullable=False),
        sa.Column("source_notes", postgresql.JSONB(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )
    op.create_table(
        "publication_events",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "question_version_id", sa.Uuid(), sa.ForeignKey("question_versions.id"), nullable=False
        ),
        sa.Column("published_by", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("idempotency_key", sa.String(120), nullable=False, unique=True),
        sa.Column("source_revision", sa.String(64), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column(
            "published_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )
    op.create_table(
        "content_embeddings",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "question_version_id",
            sa.Uuid(),
            sa.ForeignKey("question_versions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("provider", sa.String(100), nullable=False),
        sa.Column("model_identifier", sa.String(160), nullable=False),
        sa.Column("model_version", sa.String(100), nullable=False),
        sa.Column("embedding_dimension", sa.Integer(), nullable=False),
        sa.Column("source_content_hash", sa.String(64), nullable=False),
        sa.Column("embedding", Vector(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.UniqueConstraint(
            "question_version_id",
            "provider",
            "model_identifier",
            "model_version",
            "source_content_hash",
            name="uq_content_embedding_model_source",
        ),
        sa.CheckConstraint("embedding_dimension > 0", name="ck_embedding_dimension_positive"),
    )


def downgrade() -> None:
    op.drop_table("content_embeddings")
    op.drop_table("publication_events")
    op.drop_table("provenance_records")
    op.drop_table("review_decisions")
    op.drop_table("review_assignments")
    op.drop_table("validation_runs")
    op.drop_table("rubric_dimensions")
    op.drop_table("rubrics")
    op.drop_table("solutions")
    op.drop_table("question_prerequisites")
    op.drop_table("learning_objectives")
    op.drop_table("question_company_tags")
    op.drop_table("question_skills")
    op.drop_constraint("fk_questions_published_version", "questions", type_="foreignkey")
    op.drop_table("question_versions")
    op.drop_table("questions")
    op.drop_table("company_style_tags")
    op.drop_table("skills")
    op.drop_table("question_tracks")
    op.drop_table("consent_records")
    op.drop_table("organization_memberships")
    op.drop_index("uq_users_active_email", table_name="users")
    op.drop_table("users")
    op.drop_table("organizations")
    review_outcome.drop(op.get_bind())
    review_kind.drop(op.get_bind())
    content_state.drop(op.get_bind())
