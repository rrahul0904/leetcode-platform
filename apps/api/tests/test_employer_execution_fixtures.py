"""Contract tests for confidential test-bundle authoring (no code execution)."""

from __future__ import annotations

import hashlib
import json

from pydantic import ValidationError
import pytest

from rigor_api.employer_execution_fixture_routes import PrivateCodeBundle


def payload() -> dict:
    return {
        "language": "python",
        "cases": [
            {
                "case_id": "sample_one", "visibility": "sample",
                "input_data": "1\n", "expected_output": "1\n", "points": 0,
            },
            {
                "case_id": "hidden_one", "visibility": "hidden",
                "input_data": "9\n", "expected_output": "81\n", "points": 100,
            },
        ],
    }


def test_private_bundle_requires_sample_and_hidden_cases() -> None:
    value = PrivateCodeBundle.model_validate(payload())
    assert len(value.cases) == 2
    assert sum(item.points for item in value.cases) == 100
    hidden_only = payload()
    hidden_only["cases"][0]["visibility"] = "hidden"
    hidden_only["cases"][0]["points"] = 1
    with pytest.raises(ValidationError, match="Both sample and hidden"):
        PrivateCodeBundle.model_validate(hidden_only)


def test_private_bundle_enforces_identifiers_and_weighted_secrecy() -> None:
    repeated = payload()
    repeated["cases"][1]["case_id"] = "sample_one"
    with pytest.raises(ValidationError, match="unique"):
        PrivateCodeBundle.model_validate(repeated)
    wrong_sample = payload()
    wrong_sample["cases"][0]["points"] = 3
    with pytest.raises(ValidationError, match="zero marks"):
        PrivateCodeBundle.model_validate(wrong_sample)
    unscored_hidden = payload()
    unscored_hidden["cases"][1]["points"] = 0
    with pytest.raises(ValidationError, match="positive marks"):
        PrivateCodeBundle.model_validate(unscored_hidden)


def test_code_bundle_rejects_unsupported_runtime_and_fields() -> None:
    unsupported = payload()
    unsupported["language"] = "javascript"
    with pytest.raises(ValidationError):
        PrivateCodeBundle.model_validate(unsupported)
    extra = payload()
    extra["candidate_answer_key"] = "do-not-leak"
    with pytest.raises(ValidationError):
        PrivateCodeBundle.model_validate(extra)


def test_bundle_receipt_digest_is_deterministic_for_canonical_source() -> None:
    value = PrivateCodeBundle.model_validate(payload())
    canonical = json.dumps(value.model_dump(), sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(canonical.encode()).hexdigest()
    assert len(digest) == 64
    assert digest == hashlib.sha256(canonical.encode()).hexdigest()
