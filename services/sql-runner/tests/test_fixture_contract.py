from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType
from uuid import UUID

RUNNER_PATH = Path(__file__).resolve().parents[1] / "runner.py"


def load_runner() -> ModuleType:
    spec = importlib.util.spec_from_file_location("rigor_sql_runner_fixture", RUNNER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load SQL runner module.")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_parse_request_preserves_per_test_ddl_and_seed(tmp_path: Path) -> None:
    runner = load_runner()
    execution_id = UUID("55555555-5555-5555-5555-555555555555")
    request_path = tmp_path / "request.json"
    request_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "execution_id": str(execution_id),
                "attempt": 1,
                "source_code": "SELECT value FROM fixture_values ORDER BY value",
                "schema_sql": "CREATE TABLE base_values (value integer)",
                "seed_sql": "INSERT INTO base_values VALUES (99)",
                "statement_timeout_ms": 1000,
                "tests": [
                    {
                        "id": "public-2",
                        "visibility": "public",
                        "input": {
                            "ddl": "CREATE TABLE fixture_values (value integer)",
                            "seed": "INSERT INTO fixture_values VALUES (1), (2)",
                        },
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    parsed = runner.parse_request(request_path, execution_id)

    assert parsed["tests"] == [
        {
            "id": "public-2",
            "visibility": "public",
            "schema_sql": "CREATE TABLE fixture_values (value integer)",
            "seed_sql": "INSERT INTO fixture_values VALUES (1), (2)",
            "setup_sql": "",
        }
    ]
