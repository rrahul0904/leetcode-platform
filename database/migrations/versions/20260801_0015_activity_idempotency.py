"""Use a partial unique index for non-null activity idempotency keys.

Revision ID: 20260801_0015
Revises: 20260801_0014
Create Date: 2026-08-01
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "20260801_0015"
down_revision: str | None = "20260801_0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint(
        "uq_knowledge_activity_idempotency",
        "knowledge_activity_events",
        type_="unique",
    )
    op.execute(
        """
        CREATE UNIQUE INDEX uq_knowledge_activity_idempotency
        ON knowledge_activity_events (candidate_id, idempotency_key)
        WHERE idempotency_key IS NOT NULL
        """
    )


def downgrade() -> None:
    op.drop_index(
        "uq_knowledge_activity_idempotency",
        table_name="knowledge_activity_events",
    )
    op.create_unique_constraint(
        "uq_knowledge_activity_idempotency",
        "knowledge_activity_events",
        ["candidate_id", "idempotency_key"],
    )
