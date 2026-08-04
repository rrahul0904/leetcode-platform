import json
from pathlib import Path

from scripts.import_source_backed_question_bank import _difficulty, _frequency, _language
from scripts.install_source_backed_question_bank import EXPECTED

ROOT = Path(__file__).resolve().parents[2]


def test_generated_inventory_manifest_matches_uploaded_archives() -> None:
    manifest = json.loads(
        (ROOT / "content" / "imported" / "source-backed" / "manifest.json").read_text(
            encoding="utf-8"
        )
    )
    for key, expected in EXPECTED.items():
        assert manifest[key] == expected


def test_source_bank_normalization_contract() -> None:
    assert _difficulty("EASY") == "easy"
    assert _difficulty("intermediate") == "medium"
    assert _difficulty("unknown") is None
    assert _language("py") == "python"
    assert _language("cpp") == "cpp"
    assert _frequency("87.5%") == 87.5
    assert _frequency(12) == 12.0
    assert _frequency("") is None
