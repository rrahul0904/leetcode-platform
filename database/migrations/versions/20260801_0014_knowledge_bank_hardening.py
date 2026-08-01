"""Harden knowledge-bank import identity and publication grants.

Revision ID: 20260801_0014
Revises: 20260801_0013
Create Date: 2026-08-01
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260801_0014"
down_revision: str | None = "20260801_0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "UPDATE knowledge_company_observations "
        "SET observation_window='unspecified' WHERE observation_window IS NULL"
    )
    op.alter_column(
        "knowledge_company_observations",
        "observation_window",
        existing_type=sa.String(length=120),
        nullable=False,
        server_default=sa.text("'unspecified'"),
    )

    # Publication remains permission-gated by FastAPI. These narrow grants allow
    # that authorized endpoint to promote reviewed records without giving the
    # candidate role broad import or source-management privileges.
    op.execute("GRANT UPDATE (publication_status, review_status, updated_at) ON knowledge_problems TO rigor_app")
    op.execute("GRANT UPDATE (review_status, updated_at) ON knowledge_solutions TO rigor_app")


def downgrade() -> None:
    op.execute("REVOKE UPDATE (review_status, updated_at) ON knowledge_solutions FROM rigor_app")
    op.execute(
        "REVOKE UPDATE (publication_status, review_status, updated_at) "
        "ON knowledge_problems FROM rigor_app"
    )
    op.alter_column(
        "knowledge_company_observations",
        "observation_window",
        existing_type=sa.String(length=120),
        nullable=True,
        server_default=None,
    )
