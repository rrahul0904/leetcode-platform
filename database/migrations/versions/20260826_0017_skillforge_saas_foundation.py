"""Add SkillForge SaaS identity, governance, files, and commercial foundation.

Revision ID: 20260826_0017
Revises: 20260824_0016
Create Date: 2026-08-26
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260826_0017"
down_revision: str | None = "20260824_0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def uuid_pk() -> sa.Column[sa.Uuid]:
    return sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()"))


def timestamp(name: str, *, nullable: bool = False) -> sa.Column[sa.DateTime]:
    return sa.Column(
        name,
        sa.DateTime(timezone=True),
        nullable=nullable,
        server_default=None if nullable else sa.text("CURRENT_TIMESTAMP"),
    )


def owner_policy(table: str, owner_column: str = "user_id") -> None:
    op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"""
        CREATE POLICY {table}_owner_isolation ON {table}
        USING (
          {owner_column}=NULLIF(current_setting('rigor.user_id', true), '')::uuid
          OR (session_user='rigor_migrator'
              AND current_setting('rigor.maintenance_bypass', true)='on')
        )
        WITH CHECK (
          {owner_column}=NULLIF(current_setting('rigor.user_id', true), '')::uuid
          OR (session_user='rigor_migrator'
              AND current_setting('rigor.maintenance_bypass', true)='on')
        )
        """
    )


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("auth_provider", sa.String(40), nullable=False, server_default=sa.text("'local-oidc'")),
    )
    op.add_column(
        "users",
        sa.Column("status", sa.String(30), nullable=False, server_default=sa.text("'active'")),
    )
    op.create_check_constraint(
        "ck_users_status", "users", "status IN ('active', 'suspended', 'deleted')"
    )
    op.create_index("ix_users_auth_provider_subject", "users", ["auth_provider", "identity_subject"])

    op.create_table(
        "user_preferences",
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("timezone", sa.String(80), nullable=False, server_default=sa.text("'UTC'")),
        sa.Column("theme", sa.String(20), nullable=False, server_default=sa.text("'system'")),
        sa.Column(
            "notification_preferences",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "accessibility_preferences",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        timestamp("created_at"),
        timestamp("updated_at"),
        sa.CheckConstraint("theme IN ('system', 'dark', 'light')", name="ck_user_preferences_theme"),
    )
    owner_policy("user_preferences")

    op.create_table(
        "identity_webhook_events",
        uuid_pk(),
        sa.Column("provider", sa.String(40), nullable=False),
        sa.Column("external_event_id", sa.String(200), nullable=False, unique=True),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default=sa.text("'processing'")),
        sa.Column("error_code", sa.String(100)),
        timestamp("received_at"),
        sa.Column("processed_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint(
            "status IN ('processing', 'processed', 'ignored', 'failed')",
            name="ck_identity_webhook_status",
        ),
    )
    op.create_index(
        "ix_identity_webhook_events_provider_time",
        "identity_webhook_events",
        ["provider", "received_at"],
    )

    op.create_table(
        "login_events",
        uuid_pk(),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("auth_provider", sa.String(40), nullable=False),
        sa.Column("external_subject", sa.String(255), nullable=False),
        sa.Column("session_reference", sa.String(255)),
        sa.Column("success", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("correlation_id", sa.String(100)),
        timestamp("created_at"),
    )
    op.create_index("ix_login_events_user_time", "login_events", ["user_id", "created_at"])
    op.create_index(
        "ix_login_events_external_subject_time",
        "login_events",
        ["external_subject", "created_at"],
    )

    op.create_table(
        "candidate_files",
        uuid_pk(),
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("storage_key", sa.String(1024), nullable=False, unique=True),
        sa.Column("file_name", sa.String(255), nullable=False),
        sa.Column("mime_type", sa.String(160), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("checksum_sha256", sa.String(64)),
        sa.Column("category", sa.String(40), nullable=False, server_default=sa.text("'other'")),
        sa.Column("status", sa.String(30), nullable=False, server_default=sa.text("'pending_upload'")),
        timestamp("created_at"),
        timestamp("updated_at"),
        sa.CheckConstraint("size_bytes >= 0", name="ck_candidate_files_size"),
        sa.CheckConstraint(
            "category IN ('resume', 'profile_image', 'certificate', 'report', 'export', 'other')",
            name="ck_candidate_files_category",
        ),
        sa.CheckConstraint(
            "status IN ('pending_upload', 'available', 'quarantined', 'deleted')",
            name="ck_candidate_files_status",
        ),
    )
    op.create_index("ix_candidate_files_user_created", "candidate_files", ["user_id", "created_at"])
    owner_policy("candidate_files")

    op.create_table(
        "generated_reports",
        uuid_pk(),
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("report_type", sa.String(80), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default=sa.text("'queued'")),
        sa.Column("storage_key", sa.String(1024)),
        sa.Column("parameters", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        timestamp("created_at"),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint(
            "status IN ('queued', 'running', 'completed', 'failed', 'expired')",
            name="ck_generated_reports_status",
        ),
    )
    owner_policy("generated_reports")

    op.create_table(
        "data_export_requests",
        uuid_pk(),
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("format", sa.String(20), nullable=False, server_default=sa.text("'json'")),
        sa.Column("status", sa.String(30), nullable=False, server_default=sa.text("'requested'")),
        sa.Column("storage_key", sa.String(1024)),
        timestamp("created_at"),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("format IN ('json', 'csv', 'zip')", name="ck_data_export_format"),
        sa.CheckConstraint(
            "status IN ('requested', 'running', 'completed', 'failed', 'expired')",
            name="ck_data_export_status",
        ),
    )
    owner_policy("data_export_requests")

    op.create_table(
        "deletion_requests",
        uuid_pk(),
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("status", sa.String(30), nullable=False, server_default=sa.text("'requested'")),
        sa.Column("reason", sa.Text()),
        timestamp("created_at"),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint(
            "status IN ('requested', 'approved', 'processing', 'completed', 'rejected')",
            name="ck_deletion_requests_status",
        ),
    )
    owner_policy("deletion_requests")

    op.create_table(
        "plans",
        uuid_pk(),
        sa.Column("slug", sa.String(80), nullable=False, unique=True),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("price_cents", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("billing_interval", sa.String(20), nullable=False, server_default=sa.text("'month'")),
        sa.Column("features", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        timestamp("created_at"),
        timestamp("updated_at"),
        sa.CheckConstraint("price_cents >= 0", name="ck_plans_price"),
        sa.CheckConstraint(
            "billing_interval IN ('month', 'year', 'one_time')", name="ck_plans_interval"
        ),
    )
    op.create_table(
        "subscriptions",
        uuid_pk(),
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("plan_id", sa.Uuid(), sa.ForeignKey("plans.id"), nullable=False),
        sa.Column("provider", sa.String(40), nullable=False, server_default=sa.text("'stripe'")),
        sa.Column("provider_subscription_id", sa.String(255), unique=True),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("current_period_end", sa.DateTime(timezone=True)),
        timestamp("created_at"),
        timestamp("updated_at"),
        sa.CheckConstraint(
            "status IN ('trialing', 'active', 'past_due', 'paused', 'canceled', 'expired')",
            name="ck_subscriptions_status",
        ),
    )
    op.create_index("ix_subscriptions_user_status", "subscriptions", ["user_id", "status"])
    owner_policy("subscriptions")
    op.create_table(
        "entitlements",
        uuid_pk(),
        sa.Column("subscription_id", sa.Uuid(), sa.ForeignKey("subscriptions.id", ondelete="CASCADE")),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("key", sa.String(120), nullable=False),
        sa.Column("value", postgresql.JSONB(), nullable=False, server_default=sa.text("'true'::jsonb")),
        timestamp("created_at"),
        timestamp("updated_at"),
        sa.UniqueConstraint("user_id", "key", name="uq_entitlements_user_key"),
    )
    owner_policy("entitlements")

    for table in (
        "user_preferences",
        "candidate_files",
        "generated_reports",
        "data_export_requests",
        "deletion_requests",
        "subscriptions",
        "entitlements",
    ):
        op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {table} TO rigor_app")
    op.execute("GRANT SELECT, INSERT, UPDATE ON identity_webhook_events TO rigor_app")
    op.execute("GRANT SELECT, INSERT ON login_events TO rigor_app")
    op.execute("GRANT SELECT ON plans TO rigor_app")


def downgrade() -> None:
    for table in (
        "entitlements",
        "subscriptions",
        "plans",
        "deletion_requests",
        "data_export_requests",
        "generated_reports",
        "candidate_files",
        "login_events",
        "identity_webhook_events",
        "user_preferences",
    ):
        op.drop_table(table)
    op.drop_index("ix_users_auth_provider_subject", table_name="users")
    op.drop_constraint("ck_users_status", "users", type_="check")
    op.drop_column("users", "status")
    op.drop_column("users", "auth_provider")
