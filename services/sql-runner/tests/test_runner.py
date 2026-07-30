from __future__ import annotations

import importlib.util
import json
import os
import sys
from collections.abc import Iterator
from pathlib import Path
from types import ModuleType
from uuid import UUID

import psycopg
import pytest
from psycopg import sql

RUNNER_PATH = Path(__file__).resolve().parents[1] / "runner.py"
EXECUTION_ID = UUID("44444444-4444-4444-4444-444444444444")
TEST_DATABASE = "rigor_sql_runner_test"
CANDIDATE_USER = "rigor_sql_candidate_ci"


def load_runner() -> ModuleType:
    spec = importlib.util.spec_from_file_location("rigor_sql_runner", RUNNER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load SQL runner module.")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _admin_kwargs(*, database: str = "postgres") -> dict[str, object]:
    return {
        "host": os.getenv("RIGOR_SQL_TEST_HOST", "127.0.0.1"),
        "port": int(os.getenv("RIGOR_SQL_TEST_PORT", "5434")),
        "dbname": database,
        "user": os.getenv("RIGOR_SQL_TEST_USER", "rigor"),
        "password": os.getenv("RIGOR_SQL_TEST_PASSWORD", "rigor_local_only"),
        "connect_timeout": 2,
    }


@pytest.fixture(scope="module", autouse=True)
def isolated_postgres() -> Iterator[None]:
    try:
        admin = psycopg.connect(**_admin_kwargs(), autocommit=True)
    except psycopg.Error:
        pytest.skip("Local PostgreSQL integration service is unavailable.")
    with admin:
        admin.execute(
            sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(TEST_DATABASE))
        )
        admin.execute(sql.SQL("DROP ROLE IF EXISTS {}").format(sql.Identifier(CANDIDATE_USER)))
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(TEST_DATABASE)))

    previous = {
        name: os.environ.get(name)
        for name in (
            "RIGOR_SQL_HOST",
            "RIGOR_SQL_PORT",
            "RIGOR_SQL_DATABASE",
            "RIGOR_SQL_OWNER_USER",
            "RIGOR_SQL_OWNER_PASSWORD",
            "RIGOR_SQL_CANDIDATE_USER",
            "RIGOR_SQL_CANDIDATE_PASSWORD",
        )
    }
    os.environ.update(
        {
            "RIGOR_SQL_HOST": str(_admin_kwargs()["host"]),
            "RIGOR_SQL_PORT": str(_admin_kwargs()["port"]),
            "RIGOR_SQL_DATABASE": TEST_DATABASE,
            "RIGOR_SQL_OWNER_USER": str(_admin_kwargs()["user"]),
            "RIGOR_SQL_OWNER_PASSWORD": str(_admin_kwargs()["password"]),
            "RIGOR_SQL_CANDIDATE_USER": CANDIDATE_USER,
            "RIGOR_SQL_CANDIDATE_PASSWORD": "candidate-execution-only-password",
        }
    )
    try:
        yield
    finally:
        with psycopg.connect(**_admin_kwargs(), autocommit=True) as cleanup:
            cleanup.execute(
                sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(
                    sql.Identifier(TEST_DATABASE)
                )
            )
            cleanup.execute(sql.SQL("DROP ROLE IF EXISTS {}").format(sql.Identifier(CANDIDATE_USER)))
        for name, value in previous.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value


def _request(source_code: str, *, timeout_ms: int = 1_000) -> dict[str, object]:
    return {
        "attempt": 1,
        "source_code": source_code,
        "schema_sql": """
            CREATE TABLE departments (
                id integer PRIMARY KEY,
                name text NOT NULL
            );
            CREATE TABLE employees (
                id integer PRIMARY KEY,
                department_id integer REFERENCES departments(id),
                name text NOT NULL,
                salary numeric(12,2),
                manager_id integer,
                note text
            );
        """,
        "seed_sql": """
            INSERT INTO departments (id, name) VALUES (1, 'AI'), (2, 'Data');
            INSERT INTO employees (id, department_id, name, salary, manager_id, note) VALUES
              (1, 1, 'Ada', 200000.00, NULL, NULL),
              (2, 1, 'Grace', 180000.00, 1, 'compiler'),
              (3, 2, 'Linus', 170000.50, NULL, NULL),
              (4, 2, 'Margaret', 190000.00, 3, 'systems');
        """,
        "statement_timeout_ms": timeout_ms,
        "tests": [{"id": "public-1", "visibility": "public", "setup_sql": ""}],
    }


def test_parse_request_rejects_expected_answers(tmp_path: Path) -> None:
    runner = load_runner()
    path = tmp_path / "request.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "execution_id": str(EXECUTION_ID),
                "attempt": 1,
                "source_code": "SELECT 1",
                "schema_sql": "CREATE TABLE values_table (value integer)",
                "seed_sql": "",
                "statement_timeout_ms": 1_000,
                "tests": [
                    {
                        "id": "hidden-1",
                        "visibility": "hidden",
                        "input": None,
                        "expected_output": [{"value": 1}],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(runner.RunnerInputError, match="Expected outputs"):
        runner.parse_request(path, EXECUTION_ID)


@pytest.mark.parametrize(
    ("source", "columns", "rows"),
    [
        ("SELECT id, name FROM departments ORDER BY id", ["id", "name"], [[1, "AI"], [2, "Data"]]),
        (
            "SELECT d.name, count(*) AS employees "
            "FROM employees e JOIN departments d ON d.id=e.department_id "
            "GROUP BY d.name ORDER BY d.name",
            ["name", "employees"],
            [["AI", 2], ["Data", 2]],
        ),
        (
            "WITH paid AS (SELECT * FROM employees WHERE salary >= 180000) "
            "SELECT name FROM paid ORDER BY name",
            ["name"],
            [["Ada"], ["Grace"], ["Margaret"]],
        ),
        (
            "SELECT name, row_number() OVER (ORDER BY salary DESC) AS rank "
            "FROM employees ORDER BY rank",
            ["name", "rank"],
            [["Ada", 1], ["Margaret", 2], ["Grace", 3], ["Linus", 4]],
        ),
    ],
)
def test_sql_runner_executes_common_interview_queries(
    source: str,
    columns: list[str],
    rows: list[list[object]],
) -> None:
    runner = load_runner()

    result = runner.run_request(_request(source))

    assert result["status"] == "COMPLETED"
    assert result["tests"][0]["ok"] is True
    assert result["tests"][0]["actual"] == {"columns": columns, "rows": rows}


def test_null_and_numeric_values_are_normalized() -> None:
    runner = load_runner()

    result = runner.run_request(
        _request("SELECT note, salary FROM employees WHERE id=1")
    )

    assert result["tests"][0]["actual"] == {
        "columns": ["note", "salary"],
        "rows": [[None, 200000]],
    }


def test_statement_timeout_becomes_timeout_terminal_state() -> None:
    runner = load_runner()

    result = runner.run_request(_request("SELECT pg_sleep(2)", timeout_ms=150))

    assert result["status"] == "TIMEOUT"
    assert result["exit_code"] == 124
    assert result["tests"][0]["error_category"] == "timeout"


@pytest.mark.parametrize(
    "source",
    [
        "CREATE ROLE rigor_escape LOGIN",
        "CREATE DATABASE rigor_escape",
        "CREATE EXTENSION dblink",
        "COPY (SELECT 1) TO PROGRAM 'id'",
        "SELECT pg_read_file('/etc/passwd')",
    ],
)
def test_candidate_sql_cannot_escalate_privileges(source: str) -> None:
    runner = load_runner()

    result = runner.run_request(_request(source))

    assert result["status"] == "COMPLETED"
    assert result["tests"][0]["ok"] is False
    assert result["tests"][0]["error_category"] in {
        "sql_permission_denied",
        "sql_error",
    }


def test_candidate_sql_cannot_submit_multiple_commands() -> None:
    runner = load_runner()

    result = runner.run_request(_request("SELECT 1; SELECT 2"))

    assert result["tests"][0]["ok"] is False
    assert result["tests"][0]["error_category"] == "sql_error"


def test_candidate_sql_has_no_aws_environment_projection() -> None:
    runner = load_runner()

    result = runner.run_request(
        _request("SELECT current_setting('AWS_ACCESS_KEY_ID', true) AS aws_key")
    )

    assert result["tests"][0]["actual"] == {
        "columns": ["aws_key"],
        "rows": [[None]],
    }


def test_candidate_role_cannot_connect_to_application_database() -> None:
    runner = load_runner()
    runner.run_request(_request("SELECT 1"))

    candidate_kwargs = runner._connection_kwargs(candidate=True)
    candidate_kwargs["dbname"] = "rigor"
    with pytest.raises(psycopg.Error):
        psycopg.connect(**candidate_kwargs)
