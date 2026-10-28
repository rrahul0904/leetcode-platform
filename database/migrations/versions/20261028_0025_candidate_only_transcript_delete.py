"""Restrict transcript deletion to the candidate at the PostgreSQL RLS boundary.

Revision ID: 20261028_0025
Revises: 20261027_0024
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "20261028_0025"
down_revision: str | None = "20261027_0024"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # The existing permissive tenant policy grants employer reviewer/admin SELECT
    # access, and cannot by itself safely distinguish DELETE permissions.
    # A restrictive DELETE policy is AND-ed with the original tenant policy.
    # Rigor's application role may delete only the candidate's own messages,
    # regardless of its other employer memberships or selected organization.
    op.execute(
        """
        CREATE POLICY employer_ai_messages_candidate_delete
        ON employer_ai_interview_messages
        AS RESTRICTIVE FOR DELETE TO rigor_app
        USING (
          candidate_id = NULLIF(current_setting('rigor.user_id', true), '')::uuid
        )
        """
    )


def downgrade() -> None:
    op.execute(
        "DROP POLICY IF EXISTS employer_ai_messages_candidate_delete "
        "ON employer_ai_interview_messages"
    )
