from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
QUESTIONS = ROOT / "content" / "questions"


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _question(track: str, question_id: str) -> dict[str, Any]:
    return _load(QUESTIONS / track / question_id / "question.json")


def _rubric(track: str, question_id: str) -> dict[str, Any]:
    return _load(QUESTIONS / track / question_id / "rubric.json")


def test_flagship_python_question_is_real_and_executable() -> None:
    package = QUESTIONS / "python" / "PY-0001"
    question = _question("python", "PY-0001")
    public_tests = _load(package / "tests" / "public.json")
    hidden_tests = _load(package / "tests" / "hidden.json")

    assert question["title"] == "Build a Bounded TTL-Aware LRU Cache"
    assert "monotonic" in question["problem_statement"].lower()
    assert "expires_at" in " ".join(question["assumptions"])
    assert len(question["constraints"]) >= 4
    assert question["mode_specification"]["runtime"] == "3.13"
    assert question["mode_specification"]["starter_code"].strip()
    assert len(public_tests) >= 2
    assert len(hidden_tests) >= 2
    assert any(test.get("property_name") for test in hidden_tests)
    assert (package / "test_reference.py").is_file()


def test_flagship_sql_question_has_concrete_runtime_fixtures() -> None:
    package = QUESTIONS / "sql" / "SQL-0001"
    question = _question("sql", "SQL-0001")
    rubric = _rubric("sql", "SQL-0001")
    public_tests = _load(package / "tests" / "public.json")
    hidden_tests = _load(package / "tests" / "hidden.json")
    mode = question["mode_specification"]

    assert question["title"] == "Measure Week-One Product Retention"
    prompt = question["problem_statement"].lower()
    for required in (
        "source_event_id",
        "session_started",
        "test",
        "zero retained",
        "cohort_week + 1",
    ):
        assert required in prompt

    assert mode["dialect"] == "postgresql"
    assert "create table users" in mode["ddl"].lower()
    assert "insert into activity" in mode["seed_data"].lower()
    assert len(mode["expected_result"]) >= 3
    assert len(public_tests) >= 2
    assert len(hidden_tests) >= 3
    assert all(test["input"].get("ddl") for test in hidden_tests)
    assert all(test.get("expected_output") for test in hidden_tests)
    assert "deduplicated_activity" in (package / "reference.sql").read_text().lower()
    assert sum(item["weight"] for item in rubric["dimensions"]) == 100
    assert {item["name"] for item in rubric["dimensions"]} == {
        "Cohort and retention correctness",
        "Duplicate and eligibility handling",
        "Query structure and maintainability",
        "Production-scale reasoning",
    }


def test_flagship_system_design_question_is_quantified() -> None:
    question = _question("system-design", "SD-0001")
    rubric = _rubric("system-design", "SD-0001")
    mode = question["mode_specification"]
    prompt = question["problem_statement"].lower()

    assert question["title"] == "Design a Multi-Region Notification Delivery Platform"
    for required in (
        "25 million",
        "30,000",
        "200 ms",
        "99.95%",
        "idempotent",
        "eu",
        "regional outage",
    ):
        assert required in prompt

    assert len(mode["functional_requirements"]) >= 6
    assert len(mode["non_functional_requirements"]) >= 7
    assert len(mode["scale_assumptions"]) >= 6
    assert len(mode["failure_scenarios"]) >= 7
    assert len(mode["requirement_changes"]) >= 4
    assert len(mode["expected_artifacts"]) >= 6
    assert "907 million" in mode["capacity_estimation_example"]
    assert sum(item["weight"] for item in rubric["dimensions"]) == 100
    assert len(rubric["dimensions"]) >= 6
    assert "Correctness" not in {item["name"] for item in rubric["dimensions"]}


def test_flagship_questions_do_not_use_generic_template_copy() -> None:
    paths = [
        QUESTIONS / "python" / "PY-0001" / "question.json",
        QUESTIONS / "sql" / "SQL-0001" / "question.json",
        QUESTIONS / "system-design" / "SD-0001" / "question.json",
    ]
    banned = (
        "todo",
        "lorem ipsum",
        "write a production-quality sql query",
        "design a production-grade system",
        "provides an unquantified technology list",
    )

    for path in paths:
        normalized = path.read_text(encoding="utf-8").lower()
        for phrase in banned:
            assert phrase not in normalized, f"{path}: generic phrase {phrase!r}"
