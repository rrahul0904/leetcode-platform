from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any, cast
from uuid import uuid4

import psycopg
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict, make_conninfo

from .execution import ExecutionLimits, ExecutionResult, project_results, source_quality_signals
from .schemas import HiddenTestSummary, SubmissionRuntime


@dataclass(frozen=True)
class SqlSandboxLimits:
    statement_timeout_ms: int = 2_000
    row_limit: int = 500
    output_bytes: int = 128 * 1024


class DisposablePostgresSandbox:
    """Runs candidate SQL in a newly-created database with a restricted non-owner role.

    The admin DSN must point at a dedicated sandbox PostgreSQL cluster. The
    application DSN is accepted solely so construction can reject accidental
    application-database reuse.
    """

    adapter_name = "DISPOSABLE_POSTGRESQL"

    def __init__(
        self,
        *,
        admin_dsn: str,
        restricted_dsn: str,
        application_dsn: str,
        restricted_role: str = "rigor_sql_sandbox",
        limits: SqlSandboxLimits | None = None,
    ) -> None:
        self.admin_dsn = admin_dsn
        self.restricted_dsn = restricted_dsn
        self.application_dsn = application_dsn
        self.restricted_role = restricted_role
        self.limits = limits or SqlSandboxLimits()
        admin = conninfo_to_dict(admin_dsn)
        application = conninfo_to_dict(application_dsn)
        if (
            admin.get("host") == application.get("host")
            and admin.get("port") == application.get("port")
            and admin.get("dbname") == application.get("dbname")
        ):
            raise ValueError("SQL sandbox admin DSN must not target the application database")

    @staticmethod
    def _for_database(dsn: str, database: str) -> str:
        values = conninfo_to_dict(dsn)
        values["dbname"] = database
        return make_conninfo(
            **{key: str(value) for key, value in values.items() if value is not None}
        )

    def execute(
        self,
        runtime: SubmissionRuntime,
        source: str,
        tests: list[dict[str, Any]],
        *,
        limits: ExecutionLimits | None = None,
        challenge: dict[str, Any] | None = None,
    ) -> ExecutionResult:
        started = time.monotonic()
        if runtime != SubmissionRuntime.postgresql:
            return self._error(started, tests, "unsupported_runtime")
        if not challenge or not challenge.get("ddl"):
            return self._error(started, tests, "sandbox_dataset_unavailable")
        database = f"rigor_run_{uuid4().hex}"
        created = False
        raw_results: list[dict[str, Any]] = []
        try:
            with psycopg.connect(self.admin_dsn, autocommit=True) as admin:
                admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database)))
                created = True
                admin.execute(
                    sql.SQL("REVOKE CONNECT ON DATABASE {} FROM PUBLIC").format(
                        sql.Identifier(database)
                    )
                )
                admin.execute(
                    sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(
                        sql.Identifier(database), sql.Identifier(self.restricted_role)
                    )
                )
            target_admin_dsn = self._for_database(self.admin_dsn, database)
            with psycopg.connect(target_admin_dsn, autocommit=True) as setup:
                setup.execute(cast(Any, str(challenge["ddl"])))
                if challenge.get("seed_data"):
                    setup.execute(cast(Any, str(challenge["seed_data"])))
                setup.execute(
                    sql.SQL("GRANT USAGE ON SCHEMA public TO {}").format(
                        sql.Identifier(self.restricted_role)
                    )
                )
                setup.execute(
                    sql.SQL("GRANT SELECT ON ALL TABLES IN SCHEMA public TO {}").format(
                        sql.Identifier(self.restricted_role)
                    )
                )
                setup.execute(
                    sql.SQL("REVOKE CREATE ON SCHEMA public FROM {}").format(
                        sql.Identifier(self.restricted_role)
                    )
                )
            restricted_target = self._for_database(self.restricted_dsn, database)
            expected_default = challenge.get("expected_result")
            with psycopg.connect(restricted_target) as candidate:
                candidate.execute("SET default_transaction_read_only = on")
                candidate.execute("SET search_path = public")
                candidate.execute(
                    "SELECT set_config('statement_timeout', %s, false)",
                    (f"{self.limits.statement_timeout_ms}ms",),
                )
                for test in tests:
                    with candidate.transaction(), candidate.cursor() as cursor:
                        cursor.execute(cast(Any, source))
                        if cursor.description is None:
                            raise psycopg.errors.ReadOnlySqlTransaction(
                                "candidate query must return rows"
                            )
                        columns = [column.name for column in cursor.description]
                        rows = cursor.fetchmany(self.limits.row_limit + 1)
                        if len(rows) > self.limits.row_limit:
                            raise SqlResultLimitError
                        actual = [dict(zip(columns, row, strict=True)) for row in rows]
                        encoded = json.dumps(actual, default=str).encode()
                        if len(encoded) > self.limits.output_bytes:
                            raise SqlOutputLimitError
                        expected = test.get("expected_output", expected_default)
                        raw_results.append(
                            {
                                "id": str(test["id"]),
                                "passed": actual == expected,
                                "actual": actual,
                            }
                        )
        except SqlResultLimitError:
            return self._error(started, tests, "row_limit")
        except SqlOutputLimitError:
            return self._error(started, tests, "output_limit")
        except psycopg.errors.QueryCanceled:
            return self._error(started, tests, "timeout")
        except psycopg.errors.InsufficientPrivilege:
            return self._error(started, tests, "permission_denied")
        except psycopg.errors.SyntaxError:
            return self._error(started, tests, "sql_syntax_error")
        except psycopg.Error:
            return self._error(started, tests, "sql_execution_error")
        finally:
            if created:
                self._destroy(database)
        duration = round((time.monotonic() - started) * 1000)
        return project_results(tests, raw_results, duration, source)

    def _destroy(self, database: str) -> None:
        with psycopg.connect(self.admin_dsn, autocommit=True) as admin:
            admin.execute(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                "WHERE datname = %s AND pid <> pg_backend_pid()",
                (database,),
            )
            admin.execute(sql.SQL("DROP DATABASE IF EXISTS {}").format(sql.Identifier(database)))

    @staticmethod
    def _error(
        started: float, tests: list[dict[str, Any]], category: str
    ) -> ExecutionResult:
        return ExecutionResult(
            status="error",
            public_results=[],
            hidden_summary=HiddenTestSummary(
                total=sum(test.get("visibility") != "public" for test in tests), passed=0
            ),
            error_category=category,
            duration_ms=round((time.monotonic() - started) * 1000),
            candidate_message="The query could not complete in the isolated SQL environment.",
            quality_signals={**source_quality_signals(""), "sandbox_reset": True},
        )


class SqlResultLimitError(Exception):
    pass


class SqlOutputLimitError(Exception):
    pass
