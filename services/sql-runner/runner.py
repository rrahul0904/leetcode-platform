from __future__ import annotations

import argparse
import json
import os
import time
from datetime import date, datetime
from datetime import time as dt_time
from decimal import Decimal
from pathlib import Path
from typing import Any, cast
from uuid import UUID

import psycopg
from psycopg import sql
from psycopg.errors import QueryCanceled

RESULT_PREFIX = "RIGOR_EXECUTION_RESULT:"
MAX_REQUEST_BYTES = 2 * 1024 * 1024
MAX_SOURCE_BYTES = 100_000
MAX_SETUP_BYTES = 1024 * 1024
MAX_TESTS = 100
MAX_ROWS = 10_000
MAX_RESULT_BYTES = 256 * 1024
MIN_STATEMENT_TIMEOUT_MS = 100
MAX_STATEMENT_TIMEOUT_MS = 30_000
DEFAULT_LOCK_TIMEOUT_MS = 1_000
DEFAULT_IDLE_TIMEOUT_MS = 2_000


class RunnerInputError(ValueError):
    pass


class RunnerInfrastructureError(RuntimeError):
    pass


def _required_string(value: object, *, label: str, max_bytes: int) -> str:
    if not isinstance(value, str) or not value.strip():
        raise RunnerInputError(f"{label} is required.")
    if len(value.encode("utf-8")) > max_bytes:
        raise RunnerInputError(f"{label} exceeds the execution limit.")
    return value


def _optional_string(value: object, *, label: str, max_bytes: int) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        raise RunnerInputError(f"{label} must be a string.")
    if len(value.encode("utf-8")) > max_bytes:
        raise RunnerInputError(f"{label} exceeds the execution limit.")
    return value


def _positive_int(value: object, *, label: str, maximum: int) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 1 or value > maximum:
        raise RunnerInputError(f"{label} is invalid.")
    return value


def _test_fixture(value: object) -> dict[str, str | None]:
    """Normalize legacy and canonical per-test SQL fixtures.

    Existing question packages use `input.ddl` and `input.seed`; newer runner
    payloads may use `schema_sql`, `seed_sql`, and `setup_sql`. A per-test DDL or
    seed replaces the mode-level fixture for that test, while setup_sql remains
    an optional additive step.
    """

    if value is None:
        return {"schema_sql": None, "seed_sql": None, "setup_sql": ""}
    if isinstance(value, str):
        return {
            "schema_sql": None,
            "seed_sql": None,
            "setup_sql": _optional_string(
                value,
                label="Test setup SQL",
                max_bytes=MAX_SETUP_BYTES,
            ),
        }
    if isinstance(value, dict):
        schema_value = value.get("schema_sql", value.get("ddl"))
        seed_present = "seed_sql" in value or "seed" in value
        seed_value = value.get("seed_sql", value.get("seed")) if seed_present else None
        setup_value = value.get("setup_sql", "")
        schema_sql = (
            _optional_string(
                schema_value,
                label="Test schema SQL",
                max_bytes=MAX_SETUP_BYTES,
            )
            if schema_value is not None
            else None
        )
        seed_sql = (
            _optional_string(
                seed_value,
                label="Test seed SQL",
                max_bytes=MAX_SETUP_BYTES,
            )
            if seed_present
            else None
        )
        setup_sql = _optional_string(
            setup_value,
            label="Test setup SQL",
            max_bytes=MAX_SETUP_BYTES,
        )
        return {
            "schema_sql": schema_sql,
            "seed_sql": seed_sql,
            "setup_sql": setup_sql,
        }
    raise RunnerInputError(
        "SQL test input must be null, SQL text, or an object containing ddl/seed/setup_sql."
    )


def parse_request(path: Path, expected_execution_id: UUID) -> dict[str, Any]:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise RunnerInputError("Execution input is unavailable.") from exc
    if len(raw) > MAX_REQUEST_BYTES:
        raise RunnerInputError("Execution input exceeds the transport limit.")
    try:
        decoded: object = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RunnerInputError("Execution input is invalid JSON.") from exc
    if not isinstance(decoded, dict):
        raise RunnerInputError("Execution input must be a JSON object.")
    payload = decoded
    if payload.get("schema_version") != 1:
        raise RunnerInputError("Unsupported execution input schema version.")
    if payload.get("execution_id") != str(expected_execution_id):
        raise RunnerInputError("Execution input identifier mismatch.")

    attempt = _positive_int(payload.get("attempt"), label="Execution attempt", maximum=100)
    source = _required_string(
        payload.get("source_code"),
        label="Candidate SQL",
        max_bytes=MAX_SOURCE_BYTES,
    )
    schema_sql = _required_string(
        payload.get("schema_sql"),
        label="Trusted schema SQL",
        max_bytes=MAX_SETUP_BYTES,
    )
    seed_sql = _optional_string(
        payload.get("seed_sql"),
        label="Trusted seed SQL",
        max_bytes=MAX_SETUP_BYTES,
    )
    statement_timeout_ms = _positive_int(
        payload.get("statement_timeout_ms"),
        label="Statement timeout",
        maximum=MAX_STATEMENT_TIMEOUT_MS,
    )
    if statement_timeout_ms < MIN_STATEMENT_TIMEOUT_MS:
        raise RunnerInputError("Statement timeout is below the server minimum.")

    raw_tests = payload.get("tests")
    if not isinstance(raw_tests, list) or not raw_tests or len(raw_tests) > MAX_TESTS:
        raise RunnerInputError("SQL execution requires a bounded non-empty test list.")
    tests: list[dict[str, object]] = []
    seen: set[str] = set()
    for raw_test in raw_tests:
        if not isinstance(raw_test, dict):
            raise RunnerInputError("Each SQL test must be an object.")
        test_id = raw_test.get("id")
        visibility = raw_test.get("visibility", "hidden")
        if not isinstance(test_id, str) or not test_id or test_id in seen:
            raise RunnerInputError("SQL test identifiers must be non-empty and unique.")
        if visibility not in {"public", "hidden"}:
            raise RunnerInputError("SQL test visibility is invalid.")
        if "expected_output" in raw_test or "expected" in raw_test:
            raise RunnerInputError("Expected outputs must never enter the SQL sandbox.")
        seen.add(test_id)
        fixture = _test_fixture(raw_test.get("input"))
        tests.append(
            {
                "id": test_id,
                "visibility": visibility,
                **fixture,
            }
        )

    return {
        "attempt": attempt,
        "source_code": source,
        "schema_sql": schema_sql,
        "seed_sql": seed_sql,
        "statement_timeout_ms": statement_timeout_ms,
        "lock_timeout_ms": min(DEFAULT_LOCK_TIMEOUT_MS, statement_timeout_ms),
        "idle_timeout_ms": max(DEFAULT_IDLE_TIMEOUT_MS, statement_timeout_ms),
        "tests": tests,
    }


def _json_value(value: object) -> object:
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if value == float("inf"):
            return "Infinity"
        if value == float("-inf"):
            return "-Infinity"
        if value != value:
            return "NaN"
        return value
    if isinstance(value, Decimal):
        if value.is_nan():
            return "NaN"
        if value.is_infinite():
            return "Infinity" if value > 0 else "-Infinity"
        integral = value.to_integral_value()
        return int(integral) if value == integral else float(value)
    if isinstance(value, (date, datetime, dt_time)):
        return value.isoformat()
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, bytes):
        return value.hex()
    if isinstance(value, list):
        return [_json_value(item) for item in value]
    if isinstance(value, tuple):
        return [_json_value(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    return str(value)


def _connection_kwargs(*, candidate: bool = False) -> dict[str, object]:
    password_name = "RIGOR_SQL_CANDIDATE_PASSWORD" if candidate else "RIGOR_SQL_OWNER_PASSWORD"
    user_name = "RIGOR_SQL_CANDIDATE_USER" if candidate else "RIGOR_SQL_OWNER_USER"
    password = os.getenv(password_name, "")
    if not password:
        raise RunnerInfrastructureError(f"{password_name} is required.")
    return {
        "host": os.getenv("RIGOR_SQL_HOST", "127.0.0.1"),
        "port": int(os.getenv("RIGOR_SQL_PORT", "5432")),
        "dbname": os.getenv("RIGOR_SQL_DATABASE", "rigor_execution"),
        "user": os.getenv(user_name, "rigor_sql_candidate" if candidate else "rigor_sql_owner"),
        "password": password,
        "connect_timeout": 2,
    }


def wait_for_database(timeout_seconds: float = 10.0) -> None:
    deadline = time.monotonic() + timeout_seconds
    while True:
        try:
            with psycopg.connect(**_connection_kwargs()) as connection:
                connection.execute("SELECT 1")
                return
        except psycopg.Error as exc:
            if time.monotonic() >= deadline:
                raise RunnerInfrastructureError(
                    "Disposable PostgreSQL did not become ready."
                ) from exc
            time.sleep(0.1)


def _candidate_identifier() -> sql.Identifier:
    return sql.Identifier(os.getenv("RIGOR_SQL_CANDIDATE_USER", "rigor_sql_candidate"))


def ensure_candidate_role(connection: psycopg.Connection[Any]) -> None:
    candidate_user = os.getenv("RIGOR_SQL_CANDIDATE_USER", "rigor_sql_candidate")
    candidate_password = os.getenv("RIGOR_SQL_CANDIDATE_PASSWORD", "")
    if not candidate_password:
        raise RunnerInfrastructureError("RIGOR_SQL_CANDIDATE_PASSWORD is required.")
    exists = connection.execute(
        "SELECT 1 FROM pg_roles WHERE rolname=%s",
        (candidate_user,),
    ).fetchone()
    candidate = sql.Identifier(candidate_user)
    if exists:
        connection.execute(sql.SQL("DROP OWNED BY {} CASCADE").format(candidate))
        connection.execute(sql.SQL("DROP ROLE {}").format(candidate))
    connection.execute(
        sql.SQL(
            "CREATE ROLE {} LOGIN PASSWORD {} NOSUPERUSER NOCREATEDB NOCREATEROLE "
            "NOINHERIT NOREPLICATION NOBYPASSRLS"
        ).format(candidate, sql.Literal(candidate_password))
    )


def reset_fixture(
    connection: psycopg.Connection[Any],
    *,
    schema_sql: str,
    seed_sql: str,
    setup_sql: str,
) -> None:
    candidate = _candidate_identifier()
    database_name = connection.info.dbname
    if not database_name:
        raise RunnerInfrastructureError("Disposable PostgreSQL database name is unavailable.")
    database = sql.Identifier(database_name)
    connection.execute("DROP SCHEMA IF EXISTS public CASCADE")
    connection.execute("CREATE SCHEMA public")
    connection.execute("REVOKE ALL ON SCHEMA public FROM PUBLIC")
    connection.execute(sql.SQL("REVOKE ALL ON DATABASE {} FROM PUBLIC").format(database))
    connection.execute(sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(database, candidate))
    connection.execute(sql.SQL("GRANT USAGE ON SCHEMA public TO {}").format(candidate))
    connection.execute(schema_sql)
    if seed_sql.strip():
        connection.execute(seed_sql)
    if setup_sql.strip():
        connection.execute(setup_sql)
    connection.execute(
        sql.SQL("GRANT SELECT ON ALL TABLES IN SCHEMA public TO {}").format(candidate)
    )
    connection.execute(
        sql.SQL("GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {}").format(candidate)
    )


def _candidate_error_category(exc: psycopg.Error) -> str:
    if isinstance(exc, QueryCanceled) or exc.sqlstate == "57014":
        return "timeout"
    if exc.sqlstate == "42501":
        return "sql_permission_denied"
    if exc.sqlstate == "42601":
        return "sql_syntax_error"
    return "sql_error"


def execute_candidate_query(source_code: str, *, statement_timeout_ms: int) -> dict[str, object]:
    try:
        with psycopg.connect(**_connection_kwargs(candidate=True), autocommit=True) as connection:
            connection.execute(
                "SELECT set_config('statement_timeout', %s, false)",
                (f"{statement_timeout_ms}ms",),
            )
            connection.execute(
                "SELECT set_config('lock_timeout', %s, false)",
                (f"{min(DEFAULT_LOCK_TIMEOUT_MS, statement_timeout_ms)}ms",),
            )
            connection.execute(
                "SELECT set_config('idle_in_transaction_session_timeout', %s, false)",
                (f"{max(DEFAULT_IDLE_TIMEOUT_MS, statement_timeout_ms)}ms",),
            )
            with connection.cursor() as cursor:
                # Extended-query prepared execution deliberately rejects multiple
                # commands. Privileges, not SQL keyword parsing, enforce safety.
                cursor.execute(source_code, prepare=True)
                if cursor.description is None:
                    actual: object = {"columns": [], "rows": []}
                else:
                    columns = [column.name for column in cursor.description]
                    rows = cursor.fetchmany(MAX_ROWS + 1)
                    if len(rows) > MAX_ROWS:
                        return {
                            "ok": False,
                            "actual": None,
                            "error_category": "result_row_limit",
                        }
                    actual = {
                        "columns": columns,
                        "rows": [[_json_value(value) for value in row] for row in rows],
                    }
                encoded = json.dumps(actual, separators=(",", ":"), ensure_ascii=False).encode(
                    "utf-8"
                )
                if len(encoded) > MAX_RESULT_BYTES:
                    return {
                        "ok": False,
                        "actual": None,
                        "error_category": "result_size_limit",
                    }
                return {"ok": True, "actual": actual, "error_category": None}
    except psycopg.Error as exc:
        return {
            "ok": False,
            "actual": None,
            "error_category": _candidate_error_category(exc),
        }


def run_request(request: dict[str, Any]) -> dict[str, object]:
    started = time.monotonic()
    wait_for_database()
    tests = cast(list[dict[str, object]], request["tests"])
    results: list[dict[str, object]] = []
    terminal_status = "COMPLETED"

    with psycopg.connect(**_connection_kwargs(), autocommit=True) as owner:
        ensure_candidate_role(owner)
        for test in tests:
            test_schema = test.get("schema_sql")
            test_seed = test.get("seed_sql")
            reset_fixture(
                owner,
                schema_sql=(
                    str(test_schema)
                    if isinstance(test_schema, str) and test_schema.strip()
                    else str(request["schema_sql"])
                ),
                seed_sql=(
                    str(test_seed) if isinstance(test_seed, str) else str(request["seed_sql"])
                ),
                setup_sql=str(test.get("setup_sql") or ""),
            )
            outcome = execute_candidate_query(
                str(request["source_code"]),
                statement_timeout_ms=int(request["statement_timeout_ms"]),
            )
            category = outcome["error_category"]
            if category == "timeout":
                terminal_status = "TIMEOUT"
            results.append(
                {
                    "id": str(test["id"]),
                    "visibility": str(test["visibility"]),
                    "ok": bool(outcome["ok"]),
                    "actual": outcome["actual"],
                    "error_category": category,
                }
            )
            if terminal_status == "TIMEOUT":
                break

    runtime_ms = round((time.monotonic() - started) * 1000)
    return {
        "schema_version": 1,
        "attempt": int(request["attempt"]),
        "status": terminal_status,
        "runtime_ms": runtime_ms,
        "exit_code": 124 if terminal_status == "TIMEOUT" else 0,
        "tests": results,
        "stdout": "",
        "stderr": "",
        "error_category": "timeout" if terminal_status == "TIMEOUT" else None,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Rigor isolated PostgreSQL execution runner")
    parser.add_argument("--execution-id", required=True)
    parser.add_argument("--input", required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    attempt = 0
    try:
        execution_id = UUID(args.execution_id)
        request = parse_request(Path(args.input), execution_id)
        attempt = int(request["attempt"])
        result = run_request(request)
    except RunnerInputError as exc:
        result = {
            "schema_version": 1,
            "attempt": attempt,
            "status": "FAILED",
            "runtime_ms": 0,
            "exit_code": 2,
            "tests": [],
            "stdout": "",
            "stderr": "",
            "error_category": exc.__class__.__name__,
        }
    except (RunnerInfrastructureError, psycopg.Error):
        result = {
            "schema_version": 1,
            "attempt": attempt,
            "status": "FAILED",
            "runtime_ms": 0,
            "exit_code": 3,
            "tests": [],
            "stdout": "",
            "stderr": "",
            "error_category": "runner_infrastructure_error",
        }

    result["execution_id"] = str(args.execution_id)
    print(
        RESULT_PREFIX + json.dumps(result, separators=(",", ":"), ensure_ascii=False),
        flush=True,
    )
    return 0 if result.get("status") == "COMPLETED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
