"""Harden knowledge-bank import identity and publication grants.

Revision ID: 20260801_0014
Revises: 20260801_0013
Create Date: 2026-08-01
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "20260801_0014"
down_revision: str | None = "20260801_0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # PostgreSQL unique constraints normally treat NULL windows as distinct,
    # allowing the same all-time observation to be inserted repeatedly. PG18's
    # NULLS NOT DISTINCT index preserves idempotency without inventing a window.
    op.drop_constraint(
        "uq_knowledge_company_observation",
        "knowledge_company_observations",
        type_="unique",
    )
    op.execute(
        """
        CREATE UNIQUE INDEX uq_knowledge_company_observation
        ON knowledge_company_observations (
          problem_id, company_id, observation_window, source_hash
        ) NULLS NOT DISTINCT
        """
    )

    # Activity retries are idempotent only when a key is present. A partial
    # index permits unlimited normal events with NULL keys and exactly one event
    # per candidate/key pair when clients retry a network request.
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

    # Publication remains permission-gated by FastAPI. These narrow grants allow
    # that authorized endpoint to promote reviewed records without giving the
    # candidate role broad import or source-management privileges.
    op.execute(
        "GRANT UPDATE (publication_status, review_status, updated_at) "
        "ON knowledge_problems TO rigor_app"
    )
    op.execute(
        "GRANT UPDATE (review_status, updated_at) "
        "ON knowledge_solutions TO rigor_app"
    )


def downgrade() -> None:
    op.execute("REVOKE UPDATE (review_status, updated_at) ON knowledge_solutions FROM rigor_app")
    op.execute(
        "REVOKE UPDATE (publication_status, review_status, updated_at) "
        "ON knowledge_problems FROM rigor_app"
    )

    op.drop_index(
        "uq_knowledge_activity_idempotency",
        table_name="knowledge_activity_events",
    )
    op.create_unique_constraint(
        "uq_knowledge_activity_idempotency",
        "knowledge_activity_events",
        ["candidate_id", "idempotency_key"],
    )

    op.drop_index(
        "uq_knowledge_company_observation",
        table_name="knowledge_company_observations",
    )
    op.create_unique_constraint(
        "uq_knowledge_company_observation",
        "knowledge_company_observations",
        ["problem_id", "company_id", "observation_window", "source_hash"],
    )
