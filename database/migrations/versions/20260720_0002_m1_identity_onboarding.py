"""Add application roles, onboarding, and audit events.

Revision ID: 20260720_0002
Revises: 20260720_0001
Create Date: 2026-07-20
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260720_0002"
down_revision: str | None = "20260720_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("last_login_at", sa.DateTime(timezone=True)))
    op.create_table(
        "user_roles",
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("role_slug", sa.String(80), primary_key=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.CheckConstraint(
            "role_slug IN ('candidate', 'content-author', 'technical-reviewer', "
            "'editorial-reviewer', 'platform-administrator')",
            name="ck_user_roles_known_role",
        ),
    )
    op.create_table(
        "candidate_profiles",
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("target_roles", postgresql.JSONB(), nullable=False),
        sa.Column("target_companies", postgresql.JSONB(), nullable=False),
        sa.Column("experience_level", sa.String(40), nullable=False),
        sa.Column("preferred_programming_language", sa.String(40), nullable=False),
        sa.Column("weekly_study_hours", sa.SmallInteger(), nullable=False),
        sa.Column("interview_date", sa.Date()),
        sa.Column("strong_areas", postgresql.JSONB(), nullable=False),
        sa.Column("weak_areas", postgresql.JSONB(), nullable=False),
        sa.Column("preparation_intensity", sa.String(40), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=False),
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
            "weekly_study_hours BETWEEN 1 AND 40",
            name="ck_candidate_profiles_weekly_hours",
        ),
        sa.CheckConstraint(
            "experience_level IN ('mid', 'senior', 'staff', 'principal', 'manager')",
            name="ck_candidate_profiles_experience",
        ),
        sa.CheckConstraint(
            "preferred_programming_language IN ('python', 'sql', 'mixed')",
            name="ck_candidate_profiles_language",
        ),
        sa.CheckConstraint(
            "preparation_intensity IN ('steady', 'focused', 'intensive')",
            name="ck_candidate_profiles_intensity",
        ),
    )
    op.create_table(
        "audit_events",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("actor_user_id", sa.Uuid(), sa.ForeignKey("users.id")),
        sa.Column("action", sa.String(120), nullable=False),
        sa.Column("resource_type", sa.String(100), nullable=False),
        sa.Column("resource_id", sa.String(255), nullable=False),
        sa.Column(
            "details", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")
        ),
        sa.Column("correlation_id", sa.String(100), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )
    op.create_index("ix_audit_events_resource", "audit_events", ["resource_type", "resource_id"])
    op.create_index("ix_audit_events_actor", "audit_events", ["actor_user_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_audit_events_actor", table_name="audit_events")
    op.drop_index("ix_audit_events_resource", table_name="audit_events")
    op.drop_table("audit_events")
    op.drop_table("candidate_profiles")
    op.drop_table("user_roles")
    op.drop_column("users", "last_login_at")
