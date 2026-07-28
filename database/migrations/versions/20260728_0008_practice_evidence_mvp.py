"""Complete the Python practice, evaluation, and readiness MVP schema.

Revision ID: 20260728_0008
Revises: 20260721_0007
Create Date: 2026-07-28
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260728_0008"
down_revision: str | None = "20260721_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("practice_sessions", sa.Column("draft_code", sa.Text()))
    op.add_column("practice_sessions", sa.Column("notes", sa.Text()))
    op.add_column(
        "practice_sessions",
        sa.Column(
            "run_count",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )
    op.add_column(
        "practice_sessions",
        sa.Column(
            "submission_count",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )
    op.add_column(
        "practice_sessions",
        sa.Column(
            "last_activity_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )
    op.create_check_constraint(
        "ck_practice_activity_counts",
        "practice_sessions",
        "run_count >= 0 AND submission_count >= 0",
    )

    op.create_table(
        "submission_evaluations",
        sa.Column(
            "id",
            sa.Uuid(),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "submission_id",
            sa.Uuid(),
            sa.ForeignKey("submissions.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("correctness_score", sa.Numeric(6, 5), nullable=False),
        sa.Column("complexity_score", sa.Numeric(6, 5), nullable=False),
        sa.Column("code_quality_score", sa.Numeric(6, 5), nullable=False),
        sa.Column("testing_score", sa.Numeric(6, 5), nullable=False),
        sa.Column("robustness_score", sa.Numeric(6, 5), nullable=False),
        sa.Column("overall_score", sa.Numeric(6, 5), nullable=False),
        sa.Column("evaluator_version", sa.String(80), nullable=False),
        sa.Column(
            "deterministic_signals",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "heuristic_signals",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.CheckConstraint(
            "correctness_score BETWEEN 0 AND 1 "
            "AND complexity_score BETWEEN 0 AND 1 "
            "AND code_quality_score BETWEEN 0 AND 1 "
            "AND testing_score BETWEEN 0 AND 1 "
            "AND robustness_score BETWEEN 0 AND 1 "
            "AND overall_score BETWEEN 0 AND 1",
            name="ck_submission_evaluation_scores",
        ),
    )
    op.execute("ALTER TABLE submission_evaluations ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE submission_evaluations FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY submission_evaluations_principal_isolation
        ON submission_evaluations
        USING (
          (session_user = 'rigor_migrator'
            AND current_setting('rigor.maintenance_bypass', true) = 'on')
          OR EXISTS (
            SELECT 1 FROM submissions s
            WHERE s.id = submission_evaluations.submission_id
          )
        )
        WITH CHECK (
          (session_user = 'rigor_migrator'
            AND current_setting('rigor.maintenance_bypass', true) = 'on')
          OR EXISTS (
            SELECT 1 FROM submissions s
            WHERE s.id = submission_evaluations.submission_id
          )
        )
        """
    )

    op.add_column(
        "candidate_competency_evidence",
        sa.Column(
            "weight",
            sa.Numeric(6, 5),
            nullable=False,
            server_default=sa.text("1"),
        ),
    )
    op.add_column(
        "candidate_competency_evidence",
        sa.Column(
            "evaluator_version",
            sa.String(80),
            nullable=False,
            server_default=sa.text("'deterministic-v1'"),
        ),
    )
    op.create_check_constraint(
        "ck_competency_evidence_weight",
        "candidate_competency_evidence",
        "weight > 0 AND weight <= 1",
    )

    op.create_table(
        "role_readiness_profiles",
        sa.Column(
            "id",
            sa.Uuid(),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("slug", sa.String(160), nullable=False, unique=True),
        sa.Column("name", sa.String(240), nullable=False),
        sa.Column(
            "competency_weights",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
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
    op.execute(
        """
        INSERT INTO role_readiness_profiles (slug, name, competency_weights)
        VALUES (
          'STAFF_AI_ENGINEER',
          'Staff AI Engineer',
          '{
            "python-engineering": 0.20,
            "distributed-systems": 0.15,
            "system-design": 0.15,
            "generative-ai": 0.15,
            "ai-infrastructure": 0.10,
            "data-architecture": 0.10,
            "sql": 0.05,
            "reliability": 0.05,
            "technical-leadership": 0.05
          }'::jsonb
        )
        """
    )


def downgrade() -> None:
    op.drop_table("role_readiness_profiles")
    op.drop_constraint(
        "ck_competency_evidence_weight",
        "candidate_competency_evidence",
        type_="check",
    )
    op.drop_column("candidate_competency_evidence", "evaluator_version")
    op.drop_column("candidate_competency_evidence", "weight")
    op.drop_table("submission_evaluations")
    op.drop_constraint("ck_practice_activity_counts", "practice_sessions", type_="check")
    op.drop_column("practice_sessions", "last_activity_at")
    op.drop_column("practice_sessions", "submission_count")
    op.drop_column("practice_sessions", "run_count")
    op.drop_column("practice_sessions", "notes")
    op.drop_column("practice_sessions", "draft_code")
