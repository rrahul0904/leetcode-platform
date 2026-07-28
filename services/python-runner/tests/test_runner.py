from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType
from uuid import UUID

import pytest


RUNNER_PATH = Path(__file__).resolve().parents[1] / "runner.py"


def load_runner() -> ModuleType:
    spec = importlib.util.spec_from_file_location("rigor_python_runner", RUNNER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load runner module.")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_parse_request_rejects_expected_outputs(tmp_path: Path) -> None:
    runner = load_runner()
    execution_id = UUID("33333333-3333-3333-3333-333333333333")
    path = tmp_path / "request.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "execution_id": str(execution_id),
                "source_code": "def solve(value): return value",
                "entrypoint": "solve",
                "tests": [
                    {
                        "id": "hidden-1",
                        "visibility": "hidden",
                        "input": [1],
                        "expected_output": 1,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(runner.RunnerInputError, match="Expected outputs"):
        runner.parse_request(path, execution_id)


def test_run_request_executes_public_and_hidden_inputs_without_leaking_hidden_stdout() -> None:
    runner = load_runner()
    request = {
        "source_code": "def solve(a, b):\n    print(f'input={a},{b}')\n    return a + b\n",
        "entrypoint": "solve",
        "tests": [
            {"id": "public-1", "visibility": "public", "input": [2, 3]},
            {"id": "hidden-1", "visibility": "hidden", "input": [40, 2]},
        ],
    }

    result = runner.run_request(request, timeout_seconds=5)

    assert result["status"] == "COMPLETED"
    assert result["tests"] == [
        {
            "id": "public-1",
            "visibility": "public",
            "ok": True,
            "actual": 5,
            "error_category": None,
        },
        {
            "id": "hidden-1",
            "visibility": "hidden",
            "ok": True,
            "actual": 42,
            "error_category": None,
        },
    ]
    assert "input=2,3" in result["stdout"]
    assert "input=40,2" not in result["stdout"]


def test_candidate_file_access_and_unsafe_imports_are_not_exposed() -> None:
    runner = load_runner()
    file_request = {
        "source_code": "def solve(value):\n    return open('/etc/passwd').read()\n",
        "entrypoint": "solve",
        "tests": [{"id": "public-1", "visibility": "public", "input": [1]}],
    }
    import_request = {
        "source_code": "import os\ndef solve(value):\n    return dict(os.environ)\n",
        "entrypoint": "solve",
        "tests": [{"id": "public-1", "visibility": "public", "input": [1]}],
    }

    file_result = runner.run_request(file_request, timeout_seconds=5)
    import_result = runner.run_request(import_request, timeout_seconds=5)

    assert file_result["tests"][0]["ok"] is False
    assert file_result["tests"][0]["error_category"] == "NameError"
    assert import_result["tests"][0]["ok"] is False
    assert import_result["tests"][0]["error_category"] == "ImportError"
    assert "AWS_ACCESS_KEY_ID" not in import_result["stdout"]
