"""Add consent-gated employer AI interview turns separate from learner tutoring.

Revision ID: 20261027_0023
Revises: 20261027_0022
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261027_0023"
down_revision: str | None = "20261027_0022"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_USER = "NULLIF(current_setting('rigor.user_id',true),'')::uuid"
_ORG = "NULLIF(current_setting('rigor.organization_id',true),'')::uuid"


def apply_rls(table: str) -> None:
    op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
    # One tenant role is sufficient to read interview evidence, but *only*
    # the candidate can create their own turns via the API's ownership checks.
    op.execute(
        f"""CREATE POLICY {table}_tenant_access ON {table}
        USING (
          (session_user='rigor_migrator'
           AND current_setting('rigor.maintenance_bypass',true)='on')
          OR (organization_id={_ORG}
              AND EXISTS (
                SELECT 1 FROM organization_memberships m
                WHERE m.organization_id={table}.organization_id
                  AND m.user_id={_USER} AND m.status='active'
                  AND m.role_slug IN ('owner','admin','reviewer','interviewer')))
          OR (candidate_id={_USER})
        )
        WITH CHECK (
          (session_user='rigor_migrator'
           AND current_setting('rigor.maintenance_bypass',true)='on')
          OR (organization_id={_ORG}
              AND EXISTS (
                SELECT 1 FROM organization_memberships m
                WHERE m.organization_id={table}.organization_id
                  AND m.user_id={_USER} AND m.status='active'
                  AND m.role_slug IN ('owner','admin','reviewer','interviewer')))
          OR (candidate_id={_USER})
        )"""
    )
    op.execute(f"GRANT SELECT, INSERT, UPDATE ON {table} TO rigor_app")


def upgrade() -> None:
    op.create_table(
        "employer_ai_interview_sessions",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("attempt_id", sa.Uuid(), nullable=False, unique=True),
        sa.Column("candidate_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("consent_version", sa.String(32), nullable=False),
        sa.Column("consent_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("pending_request_id", sa.String(120)),
        sa.Column("pending_at", sa.DateTime(timezone=True)),
        sa.Column("turn_count", sa.SmallInteger(), nullable=False, server_default="0"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            nullable=False, server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True),
            nullable=False, server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.CheckConstraint(
            "status IN ('active','withdrawn','completed')", name="ck_employer_ai_session_state"
        ),
        sa.CheckConstraint(
            "turn_count BETWEEN 0 AND 12", name="ck_employer_ai_turn_count"
        ),
        sa.UniqueConstraint(
            "id", "organization_id", "candidate_id", name="uq_employer_ai_session_scope"
        ),
        sa.ForeignKeyConstraint(
            ["attempt_id", "organization_id", "candidate_id"],
            [
                "employer_assessment_attempts.id",
                "employer_assessment_attempts.organization_id",
                "employer_assessment_attempts.candidate_id",
            ],
            name="fk_employer_ai_session_attempt_scope",
            ondelete="CASCADE",
        ),
    )
    apply_rls("employer_ai_interview_sessions")
    op.create_table(
        "employer_ai_interview_messages",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("candidate_id", sa.Uuid(), nullable=False),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("sequence_number", sa.SmallInteger(), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("request_id", sa.String(120), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            nullable=False, server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.CheckConstraint(
            "role IN ('candidate','interviewer')", name="ck_employer_ai_message_role"
        ),
        sa.CheckConstraint("char_length(content)<=4000", name="ck_employer_ai_message_size"),
        sa.UniqueConstraint(
            "session_id", "sequence_number", name="uq_employer_ai_message_sequence"
        ),
        sa.UniqueConstraint("session_id", "request_id", "role", name="uq_employer_ai_idempotency"),
        sa.ForeignKeyConstraint(
            ["session_id", "organization_id", "candidate_id"],
            [
                "employer_ai_interview_sessions.id",
                "employer_ai_interview_sessions.organization_id",
                "employer_ai_interview_sessions.candidate_id",
            ],
            name="fk_employer_ai_message_session_scope",
            ondelete="CASCADE",
        ),
    )
    apply_rls("employer_ai_interview_messages")


def downgrade() -> None:
    op.drop_table("employer_ai_interview_messages")
    op.drop_table("employer_ai_interview_sessions")
