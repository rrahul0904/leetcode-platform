import importlib
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

source_bank = importlib.import_module("scripts.import_source_backed_question_bank")
installer = importlib.import_module("scripts.install_source_backed_question_bank")

_difficulty = source_bank._difficulty
_frequency = source_bank._frequency
_language = source_bank._language
EXPECTED = installer.EXPECTED
EXPECTED_ARCHIVE_SHA256 = "9236110b4c4af1547455998e96f100ce5d2ba945bba1fd02d9194714a11a873b"


def test_generated_inventory_manifest_matches_uploaded_archives() -> None:
    manifest = json.loads(
        (ROOT / "content" / "imported" / "source-backed" / "manifest.json").read_text(
            encoding="utf-8"
        )
    )
    for key, expected in EXPECTED.items():
        assert manifest[key] == expected


def test_source_archive_checksum_is_pinned() -> None:
    assert installer.read_expected_sha256() == EXPECTED_ARCHIVE_SHA256


def test_installer_rejects_wrong_archive_checksum(tmp_path: Path) -> None:
    archive = tmp_path / "wrong.zip"
    archive.write_bytes(b"not-the-reviewed-corpus")
    with pytest.raises(ValueError, match="archive checksum mismatch"):
        installer.validate_archive(
            archive,
            expected_sha256=EXPECTED_ARCHIVE_SHA256,
        )


def test_source_bank_normalization_contract() -> None:
    assert _difficulty("EASY") == "easy"
    assert _difficulty("intermediate") == "medium"
    assert _difficulty("unknown") is None
    assert _language("py") == "python"
    assert _language("cpp") == "cpp"
    assert _frequency("87.5%") == 87.5
    assert _frequency(12) == 12.0
    assert _frequency("") is None
