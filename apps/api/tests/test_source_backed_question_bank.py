from pathlib import Path

from scripts.import_source_backed_question_bank import load_payload, validate_payload


def test_generated_source_bank_has_expected_inventory() -> None:
    archive = (
        Path(__file__).resolve().parents[2]
        / "content"
        / "imported"
        / "source-backed"
        / "question-bank.zip.b64"
    )
    payload = load_payload(archive)
    counts = validate_payload(payload)
    assert counts == {
        "problems": 3425,
        "solutions": 120,
        "company_observations": 35348,
        "system_design_articles": 29,
    }


def test_imported_problems_are_searchable_but_not_executable() -> None:
    archive = (
        Path(__file__).resolve().parents[2]
        / "content"
        / "imported"
        / "source-backed"
        / "question-bank.zip.b64"
    )
    payload = load_payload(archive)
    problems = payload["problems"]
    solutions = payload["solutions"]
    assert all(problem["disposition"] == "external_reference_only" for problem in problems)
    assert all(solution["disposition"] == "rights_review_required" for solution in solutions)
