from __future__ import annotations

import pytest

from scripts.verify_pinned_source_content import (
    VerificationError,
    parse_expectations,
    verify,
)


def test_parse_expectations() -> None:
    assert parse_expectations(["total_files=620", "code_files=462"]) == {
        "total_files": 620,
        "code_files": 462,
    }


def test_parse_expectations_rejects_invalid_value() -> None:
    with pytest.raises(VerificationError, match="invalid --expect"):
        parse_expectations(["total_files"])


def test_verify_accepts_exact_counts() -> None:
    verify({"total_files": 620, "code_files": 462}, {"total_files": 620})


def test_verify_rejects_mismatch() -> None:
    with pytest.raises(VerificationError, match="expected 620"):
        verify({"total_files": 619}, {"total_files": 620})
