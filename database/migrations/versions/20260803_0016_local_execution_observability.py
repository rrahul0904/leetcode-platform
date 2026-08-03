"""Grant the local read-only observer access to execution metric sources.

Revision ID: 20260803_0016
Revises: 20260802_0015
Create Date: 2026-08-03
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "20260803_0016"
down_revision: str | None = "20260802_0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Metrics are aggregate-only, but the observer must be able to read each
    # durable source table. The role has no mutation privileges and receives no
    # access to execution payloads, candidate source, inputs, or results.
    op.execute("GRANT SELECT ON local_execution_queue TO rigor_readonly")
    op.execute("GRANT SELECT ON local_execution_controller_status TO rigor_readonly")
    op.execute("GRANT SELECT ON execution_requests TO rigor_readonly")


def downgrade() -> None:
    op.execute("REVOKE SELECT ON local_execution_queue FROM rigor_readonly")
    # These grants may predate this migration through the default read-only
    # topology, so retain them during downgrade rather than narrowing an
    # existing operational role unexpectedly.
