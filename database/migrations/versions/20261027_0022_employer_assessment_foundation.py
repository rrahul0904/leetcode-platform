"""Add tenant-isolated employer assessments, invitations, attempts and human reviews.

Revision ID: 20261027_0022
Revises: 20260918_0021
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261027_0022"
down_revision: str | None = "20260918_0021"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def uid() -> sa.Column[sa.Uuid]:
    return sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()"))


def org() -> sa.Column[sa.Uuid]:
    return sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("organizations.id"), nullable=False)


def stamp(name: str = "created_at") -> sa.Column[sa.DateTime]:
    return sa.Column(
        name, sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")
    )


def tenant_policy(table: str, *, candidate: bool = False, privileged: bool = False) -> None:
    op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
    roles = (
        "'owner','admin','reviewer'"
        if privileged else "'owner','admin','recruiter','interviewer','reviewer'"
    )
    member = (
        "EXISTS (SELECT 1 FROM organization_memberships om "
        f"WHERE om.organization_id={table}.organization_id "
        "AND om.user_id::text=NULLIF(current_setting('rigor.user_id',true),'') "
        f"AND om.role_slug IN ({roles}) AND om.status='active')"
    )
    candidate_access = (
        " OR (candidate_id::text=NULLIF(current_setting('rigor.user_id',true),'') "
        "AND current_setting('rigor.user_id',true)<>'')"
        if candidate else ""
    )
    expression = (
        "(session_user='rigor_migrator' "
        "AND current_setting('rigor.maintenance_bypass',true)='on') "
        "OR (("
        "organization_id::text=NULLIF(current_setting('rigor.organization_id',true),'') "
        f"AND {member}){candidate_access})"
    )
    op.execute(
        f"CREATE POLICY {table}_tenant_access ON {table} "
        f"USING ({expression}) WITH CHECK ({expression})"
    )


def upgrade() -> None:
    # Organization membership status is required by the database-authoritative
    # OIDC principal and all employer routes. Backfill pre-existing memberships.
    op.add_column(
        "organization_memberships",
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
    )
    op.create_check_constraint(
        "ck_org_membership_status",
        "organization_memberships",
        "status IN ('active','suspended','revoked')",
    )
    op.create_table(
        "employer_assessment_versions",
        uid(), org(),
        sa.Column("slug", sa.String(160), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="draft"),
        sa.Column("duration_minutes", sa.SmallInteger(), nullable=False),
        sa.Column("maximum_marks", sa.Integer(), nullable=False),
        sa.Column("candidate_blueprint", postgresql.JSONB(), nullable=False),
        sa.Column("content_sha256", sa.String(64), nullable=False),
        sa.Column("created_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        stamp(),
        sa.Column("approved_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("version >= 1", name="ck_employer_assessment_version"),
        sa.CheckConstraint(
            "duration_minutes BETWEEN 5 AND 360", name="ck_employer_assessment_duration"
        ),
        sa.CheckConstraint(
            "maximum_marks BETWEEN 1 AND 1000", name="ck_employer_assessment_marks"
        ),
        sa.CheckConstraint(
            "status IN ('draft','review_required','approved','published','revoked')",
            name="ck_employer_assessment_status",
        ),
        sa.CheckConstraint(
            "content_sha256 ~ '^[0-9a-f]{64}$'", name="ck_employer_assessment_hash"
        ),
        sa.UniqueConstraint("organization_id", "slug", "version", name="uq_employer_assessment_version"),
        sa.UniqueConstraint("id", "organization_id", name="uq_employer_assessment_org_id"),
    )
    tenant_policy("employer_assessment_versions")

    op.create_table(
        "employer_assessment_private_keys",
        sa.Column(
            "assessment_version_id", sa.Uuid(),
            sa.ForeignKey("employer_assessment_versions.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        org(),
        sa.Column("private_rubric", postgresql.JSONB(), nullable=False),
        sa.Column("source_sha256", sa.String(64), nullable=False),
        stamp(),
        sa.ForeignKeyConstraint(
            ["assessment_version_id", "organization_id"],
            ["employer_assessment_versions.id", "employer_assessment_versions.organization_id"],
            name="fk_assessment_private_key_scope",
        ),
    )
    tenant_policy("employer_assessment_private_keys", privileged=True)

    op.create_table(
        "employer_assessment_invitations",
        uid(), org(),
        sa.Column("assessment_version_id", sa.Uuid(), nullable=False),
        sa.Column("candidate_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("invited_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_digest", sa.String(64), nullable=False, unique=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("state", sa.String(24), nullable=False, server_default="pending"),
        stamp(),
        sa.Column("consumed_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint(
            "state IN ('pending','accepted','revoked','expired')",
            name="ck_assessment_invitation_state",
        ),
        sa.UniqueConstraint(
            "id", "organization_id", "candidate_id",
            name="uq_assessment_invitation_org_candidate",
        ),
        sa.ForeignKeyConstraint(
            ["assessment_version_id", "organization_id"],
            ["employer_assessment_versions.id", "employer_assessment_versions.organization_id"],
            name="fk_assessment_invitation_scope",
        ),
    )
    tenant_policy("employer_assessment_invitations", candidate=True)
    # Published candidate-visible questions may be read only by the invited
    # candidate; this policy never grants read access to private answer keys.
    # Invitation RLS itself restricts this EXISTS to the candidate's own rows.
    op.execute("""
        CREATE POLICY employer_assessment_candidate_visible
        ON employer_assessment_versions FOR SELECT TO rigor_app
        USING (
          status='published' AND EXISTS (
            SELECT 1 FROM employer_assessment_invitations i
            WHERE i.assessment_version_id=employer_assessment_versions.id
              AND i.candidate_id=NULLIF(current_setting('rigor.user_id',true),'')::uuid
              AND i.state='accepted'
          )
        )
    """)
    op.create_index(
        "ix_assessment_invitation_candidate",
        "employer_assessment_invitations", ["candidate_id", "expires_at"]
    )

    op.create_table(
        "employer_assessment_attempts",
        uid(), org(),
        sa.Column("invitation_id", sa.Uuid(), nullable=False, unique=True),
        sa.Column("candidate_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(24), nullable=False, server_default="created"),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("deadline_at", sa.DateTime(timezone=True)),
        sa.Column("submitted_at", sa.DateTime(timezone=True)),
        stamp(),
        sa.CheckConstraint(
            "status IN ('created','in_progress','submitted','expired','cancelled')",
            name="ck_assessment_attempt_status",
        ),
        sa.CheckConstraint(
            "deadline_at IS NULL OR (started_at IS NOT NULL AND deadline_at>started_at)",
            name="ck_assessment_deadline",
        ),
        sa.UniqueConstraint(
            "id", "organization_id", "candidate_id", name="uq_assessment_attempt_scope"
        ),
        sa.ForeignKeyConstraint(
            ["invitation_id", "organization_id", "candidate_id"],
            [
                "employer_assessment_invitations.id",
                "employer_assessment_invitations.organization_id",
                "employer_assessment_invitations.candidate_id",
            ],
            name="fk_assessment_attempt_invitation_scope",
            ondelete="CASCADE",
        ),
    )
    tenant_policy("employer_assessment_attempts", candidate=True)

    op.create_table(
        "employer_assessment_responses",
        uid(), org(),
        sa.Column("attempt_id", sa.Uuid(), nullable=False),
        sa.Column("candidate_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("question_number", sa.SmallInteger(), nullable=False),
        sa.Column("answer_text", sa.Text(), nullable=False),
        sa.Column("answer_sha256", sa.String(64), nullable=False),
        stamp("updated_at"),
        sa.CheckConstraint(
            "question_number BETWEEN 1 AND 500", name="ck_assessment_question_number"
        ),
        sa.UniqueConstraint("attempt_id", "question_number", name="uq_assessment_response"),
        sa.ForeignKeyConstraint(
            ["attempt_id", "organization_id", "candidate_id"],
            [
                "employer_assessment_attempts.id",
                "employer_assessment_attempts.organization_id",
                "employer_assessment_attempts.candidate_id",
            ],
            name="fk_assessment_response_scope",
            ondelete="CASCADE",
        ),
    )
    tenant_policy("employer_assessment_responses", candidate=True)

    op.create_table(
        "employer_assessment_reviews",
        uid(), org(),
        sa.Column("attempt_id", sa.Uuid(), nullable=False),
        sa.Column("candidate_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("reviewer_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("evidence", postgresql.JSONB(), nullable=False),
        sa.Column("status", sa.String(24), nullable=False, server_default="draft"),
        stamp(),
        sa.CheckConstraint(
            "status IN ('draft','submitted','adjudicated')",
            name="ck_assessment_review_status",
        ),
        sa.ForeignKeyConstraint(
            ["attempt_id", "organization_id", "candidate_id"],
            [
                "employer_assessment_attempts.id",
                "employer_assessment_attempts.organization_id",
                "employer_assessment_attempts.candidate_id",
            ],
            name="fk_assessment_review_scope",
            ondelete="CASCADE",
        ),
    )
    tenant_policy("employer_assessment_reviews", privileged=True)

    for table in (
        "employer_assessment_versions",
        "employer_assessment_private_keys",
        "employer_assessment_invitations",
        "employer_assessment_attempts",
        "employer_assessment_responses",
        "employer_assessment_reviews",
    ):
        op.execute(f"GRANT SELECT, INSERT, UPDATE ON {table} TO rigor_app")

    op.execute("""
        CREATE FUNCTION employer_assessment_protect_approved() RETURNS trigger AS $$
        BEGIN
            IF TG_OP='DELETE' AND OLD.status IN ('approved','published','revoked') THEN
                RAISE EXCEPTION 'Approved assessment versions cannot be deleted';
            END IF;
            IF TG_OP='UPDATE' AND OLD.status IN ('approved','published','revoked')
               AND (
                OLD.candidate_blueprint IS DISTINCT FROM NEW.candidate_blueprint OR
                OLD.content_sha256 IS DISTINCT FROM NEW.content_sha256 OR
                OLD.duration_minutes IS DISTINCT FROM NEW.duration_minutes OR
                OLD.maximum_marks IS DISTINCT FROM NEW.maximum_marks OR
                OLD.slug IS DISTINCT FROM NEW.slug OR
                OLD.version IS DISTINCT FROM NEW.version
               )
            THEN
                RAISE EXCEPTION 'Approved assessment version content is immutable';
            END IF;
            IF TG_OP='DELETE' THEN RETURN OLD; END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)
    op.execute("""
        CREATE TRIGGER tr_employer_assessment_immutable
        BEFORE UPDATE OR DELETE ON employer_assessment_versions
        FOR EACH ROW EXECUTE FUNCTION employer_assessment_protect_approved();
    """)


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER IF EXISTS tr_employer_assessment_immutable "
        "ON employer_assessment_versions"
    )
    op.execute("DROP FUNCTION IF EXISTS employer_assessment_protect_approved()")
    for table in (
        "employer_assessment_reviews",
        "employer_assessment_responses",
        "employer_assessment_attempts",
        "employer_assessment_invitations",
        "employer_assessment_private_keys",
        "employer_assessment_versions",
    ):
        op.drop_table(table)
    op.drop_constraint(
        "ck_org_membership_status", "organization_memberships", type_="check"
    )
    op.drop_column("organization_memberships", "status")
