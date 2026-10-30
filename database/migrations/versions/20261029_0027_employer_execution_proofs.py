"""Bind employer code results to reviewed fixtures and immutable runner images.

Revision ID: 20261029_0027
Revises: 20261028_0026
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261029_0027"
down_revision: str | None = "20261028_0026"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Tenant policies on assessment, AI transcript and execution rows consult
    # memberships under rigor_app. A missing SELECT grant makes those policies
    # raise permission denied instead of returning their scoped result.
    op.execute("GRANT SELECT ON organization_memberships TO rigor_app")
    op.add_column("employer_code_executions", sa.Column("runtime_image_sha256", sa.String(64)))
    op.add_column("employer_code_executions", sa.Column("sql_postgres_image_sha256", sa.String(64)))
    op.add_column("employer_code_executions", sa.Column("result_sha256", sa.String(64)))
    op.create_check_constraint(
        "ck_employer_code_proof_hashes", "employer_code_executions",
        "(fixture_sha256 IS NULL OR fixture_sha256 ~ '^[0-9a-f]{64}$') "
        "AND (runtime_image_sha256 IS NULL OR runtime_image_sha256 ~ '^[0-9a-f]{64}$') "
        "AND (sql_postgres_image_sha256 IS NULL OR sql_postgres_image_sha256 ~ '^[0-9a-f]{64}$') "
        "AND (result_sha256 IS NULL OR result_sha256 ~ '^[0-9a-f]{64}$')",
    )
    op.execute("""
        CREATE FUNCTION protect_terminal_employer_code_execution()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          IF OLD.status IN ('completed', 'failed', 'timeout') THEN
            RAISE EXCEPTION 'terminal employer code execution is immutable';
          END IF;
          RETURN NEW;
        END
        $$
    """)
    op.execute("""
        CREATE TRIGGER trg_protect_terminal_employer_code_execution
        BEFORE UPDATE ON employer_code_executions
        FOR EACH ROW EXECUTE FUNCTION protect_terminal_employer_code_execution()
    """)


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER trg_protect_terminal_employer_code_execution "
        "ON employer_code_executions"
    )
    op.execute("DROP FUNCTION protect_terminal_employer_code_execution()")
    op.drop_constraint(
        "ck_employer_code_proof_hashes", "employer_code_executions", type_="check"
    )
    op.drop_column("employer_code_executions", "result_sha256")
    op.drop_column("employer_code_executions", "sql_postgres_image_sha256")
    op.drop_column("employer_code_executions", "runtime_image_sha256")
    op.execute("REVOKE SELECT ON organization_memberships FROM rigor_app")
