"""Add least-privilege execution worker and reconciler database access.

Revision ID: 20260729_0011
Revises: 20260729_0010
Create Date: 2026-07-29
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "20260729_0011"
down_revision: str | None = "20260729_0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


EXECUTION_TABLES = (
    "execution_requests",
    "execution_payloads",
    "execution_outbox",
    "execution_public_results",
    "execution_events",
)


def upgrade() -> None:
    # Group roles are safe to create without LOGIN. Production can grant these
    # roles to Secrets-Manager/IAM-authenticated login roles. Local development
    # creates login variants in database/init/001_roles.sql.
    op.execute(
        """
        DO $roles$
        BEGIN
          IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='rigor_execution_worker') THEN
            CREATE ROLE rigor_execution_worker NOLOGIN
              NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
          END IF;
          IF NOT EXISTS (
            SELECT 1 FROM pg_roles WHERE rolname='rigor_execution_reconciler'
          ) THEN
            CREATE ROLE rigor_execution_reconciler NOLOGIN
              NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
          END IF;
          IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='rigor_executor') THEN
            ALTER ROLE rigor_executor NOBYPASSRLS;
            GRANT rigor_execution_worker TO rigor_executor;
          END IF;
        END
        $roles$;
        """
    )

    op.execute(
        "GRANT USAGE ON SCHEMA public TO rigor_execution_worker, rigor_execution_reconciler"
    )
    op.execute(
        "GRANT SELECT, INSERT, UPDATE, DELETE ON execution_requests TO rigor_execution_worker"
    )
    op.execute(
        "GRANT SELECT, UPDATE ON execution_requests TO rigor_execution_reconciler"
    )
    op.execute("GRANT SELECT ON execution_payloads TO rigor_execution_worker")
    op.execute("GRANT SELECT ON execution_payloads TO rigor_execution_reconciler")
    op.execute("GRANT SELECT, UPDATE ON execution_outbox TO rigor_execution_worker")
    op.execute("GRANT SELECT, UPDATE ON execution_outbox TO rigor_execution_reconciler")
    op.execute(
        "GRANT SELECT, INSERT, UPDATE ON execution_public_results TO rigor_execution_worker"
    )
    op.execute(
        "GRANT SELECT, INSERT, UPDATE ON execution_public_results TO rigor_execution_reconciler"
    )
    op.execute("GRANT SELECT, INSERT ON execution_events TO rigor_execution_worker")
    op.execute("GRANT SELECT, INSERT ON execution_events TO rigor_execution_reconciler")

    for role in ("rigor_execution_worker", "rigor_execution_reconciler"):
        op.execute(f"GRANT SELECT ON question_versions TO {role}")
        op.execute(f"GRANT SELECT, UPDATE ON practice_sessions TO {role}")
        op.execute(f"GRANT SELECT, INSERT ON practice_session_events TO {role}")
        op.execute(f"GRANT SELECT, UPDATE ON submissions TO {role}")
        op.execute(f"GRANT SELECT, INSERT, UPDATE ON submission_results TO {role}")
        op.execute(f"GRANT SELECT, INSERT, UPDATE ON submission_evaluations TO {role}")

    for table in EXECUTION_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")

    op.execute(
        """
        CREATE POLICY execution_requests_worker_access
        ON execution_requests
        FOR ALL TO rigor_execution_worker
        USING (true)
        WITH CHECK (true)
        """
    )
    op.execute(
        """
        CREATE POLICY execution_requests_reconciler_select
        ON execution_requests
        FOR SELECT TO rigor_execution_reconciler
        USING (true)
        """
    )
    op.execute(
        """
        CREATE POLICY execution_requests_reconciler_update
        ON execution_requests
        FOR UPDATE TO rigor_execution_reconciler
        USING (true)
        WITH CHECK (true)
        """
    )

    for table in ("execution_payloads",):
        op.execute(
            f"""
            CREATE POLICY {table}_worker_select
            ON {table}
            FOR SELECT TO rigor_execution_worker
            USING (true)
            """
        )
        op.execute(
            f"""
            CREATE POLICY {table}_reconciler_select
            ON {table}
            FOR SELECT TO rigor_execution_reconciler
            USING (true)
            """
        )

    for table in ("execution_outbox",):
        op.execute(
            f"""
            CREATE POLICY {table}_worker_access
            ON {table}
            FOR ALL TO rigor_execution_worker
            USING (true)
            WITH CHECK (true)
            """
        )
        op.execute(
            f"""
            CREATE POLICY {table}_reconciler_access
            ON {table}
            FOR ALL TO rigor_execution_reconciler
            USING (true)
            WITH CHECK (true)
            """
        )

    for table in ("execution_public_results", "execution_events"):
        op.execute(
            f"""
            CREATE POLICY {table}_worker_access
            ON {table}
            FOR ALL TO rigor_execution_worker
            USING (true)
            WITH CHECK (true)
            """
        )
        op.execute(
            f"""
            CREATE POLICY {table}_reconciler_access
            ON {table}
            FOR ALL TO rigor_execution_reconciler
            USING (true)
            WITH CHECK (true)
            """
        )


def downgrade() -> None:
    policies = {
        "execution_requests": (
            "execution_requests_worker_access",
            "execution_requests_reconciler_select",
            "execution_requests_reconciler_update",
        ),
        "execution_payloads": (
            "execution_payloads_worker_select",
            "execution_payloads_reconciler_select",
        ),
        "execution_outbox": (
            "execution_outbox_worker_access",
            "execution_outbox_reconciler_access",
        ),
        "execution_public_results": (
            "execution_public_results_worker_access",
            "execution_public_results_reconciler_access",
        ),
        "execution_events": (
            "execution_events_worker_access",
            "execution_events_reconciler_access",
        ),
    }
    for table, names in policies.items():
        for name in names:
            op.execute(f"DROP POLICY IF EXISTS {name} ON {table}")

    for role in ("rigor_execution_worker", "rigor_execution_reconciler"):
        op.execute(f"REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA public FROM {role}")
        op.execute(f"REVOKE USAGE ON SCHEMA public FROM {role}")
