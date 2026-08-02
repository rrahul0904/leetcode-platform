"""Add the durable queue used by the local Docker execution controller.

Revision ID: 20260802_0012
Revises: 20260729_0011
Create Date: 2026-08-02
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "20260802_0012"
down_revision: str | None = "20260729_0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE local_execution_queue (
          id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          body text NOT NULL,
          visible_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
          receipt_handle uuid,
          receive_count integer NOT NULL DEFAULT 0 CHECK (receive_count >= 0),
          created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
          updated_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    op.execute(
        """
        CREATE INDEX ix_local_execution_queue_visible
        ON local_execution_queue (visible_at, created_at, id)
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX ux_local_execution_queue_receipt
        ON local_execution_queue (receipt_handle)
        WHERE receipt_handle IS NOT NULL
        """
    )
    op.execute(
        """
        CREATE TABLE local_execution_controller_status (
          controller_key text PRIMARY KEY,
          worker_id text NOT NULL,
          heartbeat_at timestamptz NOT NULL,
          queue_depth integer NOT NULL DEFAULT 0 CHECK (queue_depth >= 0),
          CHECK (controller_key = 'local')
        )
        """
    )

    op.execute(
        "GRANT SELECT, INSERT, UPDATE, DELETE ON local_execution_queue "
        "TO rigor_execution_worker"
    )
    op.execute(
        "GRANT SELECT, INSERT, UPDATE, DELETE ON local_execution_queue "
        "TO rigor_execution_reconciler"
    )
    op.execute(
        "GRANT SELECT, INSERT, UPDATE, DELETE ON local_execution_controller_status "
        "TO rigor_execution_worker"
    )
    op.execute(
        "GRANT SELECT, INSERT, UPDATE, DELETE ON local_execution_controller_status "
        "TO rigor_execution_reconciler"
    )
    op.execute("GRANT SELECT ON local_execution_controller_status TO rigor_app")
    op.execute("GRANT SELECT ON local_execution_controller_status TO rigor_readonly")

    op.execute("ALTER TABLE local_execution_queue ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE local_execution_queue FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY local_execution_queue_worker_access
        ON local_execution_queue
        FOR ALL TO rigor_execution_worker
        USING (true)
        WITH CHECK (true)
        """
    )
    op.execute(
        """
        CREATE POLICY local_execution_queue_reconciler_access
        ON local_execution_queue
        FOR ALL TO rigor_execution_reconciler
        USING (true)
        WITH CHECK (true)
        """
    )


def downgrade() -> None:
    op.execute(
        "DROP POLICY IF EXISTS local_execution_queue_reconciler_access "
        "ON local_execution_queue"
    )
    op.execute(
        "DROP POLICY IF EXISTS local_execution_queue_worker_access "
        "ON local_execution_queue"
    )
    op.execute("DROP TABLE IF EXISTS local_execution_controller_status")
    op.execute("DROP TABLE IF EXISTS local_execution_queue")
