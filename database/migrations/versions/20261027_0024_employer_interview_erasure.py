"""Permit irreversible candidate-initiated erasure of stored AI interview text.

Revision ID: 20261027_0024
Revises: 20261027_0023
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261027_0024"
down_revision: str | None = "20261027_0023"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "employer_ai_interview_sessions",
        sa.Column("erased_at", sa.DateTime(timezone=True)),
    )
    op.drop_constraint(
        "ck_employer_ai_session_state",
        "employer_ai_interview_sessions",
        type_="check",
    )
    op.create_check_constraint(
        "ck_employer_ai_session_state",
        "employer_ai_interview_sessions",
        "status IN ('active','withdrawn','completed','erased')",
    )
    # Privilege limited to the table with candidate-authored text. RLS
    # independently restricts it to the authenticated candidate/tenant.
    op.execute("GRANT DELETE ON employer_ai_interview_messages TO rigor_app")


def downgrade() -> None:
    op.execute("REVOKE DELETE ON employer_ai_interview_messages FROM rigor_app")
    # Do not reconstruct erased text. Preserve the evidence that consent was withdrawn.
    op.execute(
        """UPDATE employer_ai_interview_sessions
           SET status='withdrawn'
           WHERE status='erased'"""
    )
    op.drop_constraint(
        "ck_employer_ai_session_state",
        "employer_ai_interview_sessions",
        type_="check",
    )
    op.create_check_constraint(
        "ck_employer_ai_session_state",
        "employer_ai_interview_sessions",
        "status IN ('active','withdrawn','completed')",
    )
    op.drop_column("employer_ai_interview_sessions", "erased_at")
