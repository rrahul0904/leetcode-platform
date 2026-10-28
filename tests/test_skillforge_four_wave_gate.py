from __future__ import annotations

import copy
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from skillforge_four_wave_gate import GateError, validate  # noqa: E402

LEDGER = ROOT / "docs/platform/skillforge_four_wave_gate_status.json"
SHA = "bfc4cbdeaed3bc71cbd3aa9225ccbf4af8883976"


def baseline() -> dict:
    return json.loads(LEDGER.read_text(encoding="utf-8"))


def certified() -> dict:
    state = baseline()
    state["release_sha"] = SHA
    for wave in state["waves"]:
        wave["status"] = "verified"
    for gate in state["gates"]:
        gate["status"] = "verified"
        gate["reason"] = ""
        gate["evidence"] = [{
            "release_sha": SHA,
            "reviewer": "independent-test-reviewer",
            "evidence_url": (
                "https://github.com/rrahul0904/leetcode-platform/"
                "actions/runs/40630606777"
            ),
            "observed_at": (datetime.now(UTC) - timedelta(hours=1)).isoformat(),
            "environment": "synthetic-test-only-not-production",
            "negative_case": "synthetic forbidden cross-tenant test",
            "artifact_sha256": "a" * 64,
        }]
    return state


def test_existing_release_is_truthfully_blocked() -> None:
    report = validate(baseline())
    assert report["verified_gates"] == 0
    assert report["blocked_gates"] == 10
    assert report["verdict"] == "NO_GO_PENDING_LIVE_CERTIFICATION"
    with pytest.raises(GateError, match="NO-GO"):
        validate(baseline(), ready=True)


def test_unrecognized_and_duplicate_gates_fail_closed() -> None:
    state = baseline()
    state["gates"][1]["id"] = "L01"
    with pytest.raises(GateError, match="missing, duplicated"):
        validate(state)
    state = baseline()
    state["gates"].pop()
    with pytest.raises(GateError, match="exactly ten"):
        validate(state)


def test_wrong_production_target_or_wave_assignment_fails() -> None:
    state = baseline()
    state["production_target"] = "Vercel"
    with pytest.raises(GateError, match="must remain AWS"):
        validate(state)
    state = baseline()
    state["gates"][0]["wave"] = "W4"
    with pytest.raises(GateError, match="incorrect wave"):
        validate(state)


def test_unproven_verified_status_is_rejected() -> None:
    state = baseline()
    state["gates"][0]["status"] = "verified"
    with pytest.raises(GateError, match="requires pinned SHA and evidence"):
        validate(state)


def test_structural_proof_requires_immutable_sha_and_independent_reviewer() -> None:
    fixture = certified()  # Synthetic fixture only: never use to sign a real release.
    assert validate(fixture, ready=True, release_sha=SHA)["verified_gates"] == 10
    state = copy.deepcopy(fixture)
    state["gates"][0]["evidence"][0]["release_sha"] = "0" * 40
    with pytest.raises(GateError, match="receipt SHA"):
        validate(state, ready=True, release_sha=SHA)
    state = copy.deepcopy(fixture)
    state["gates"][0]["evidence"][0]["reviewer"] = fixture["builder"]
    with pytest.raises(GateError, match="independent reviewer"):
        validate(state, ready=True, release_sha=SHA)
    state = copy.deepcopy(fixture)
    state["gates"][0]["evidence"][0]["negative_case"] = ""
    with pytest.raises(GateError, match="negative-control"):
        validate(state)


def test_fake_link_digest_and_future_receipt_are_rejected() -> None:
    state = certified()
    receipt = state["gates"][1]["evidence"][0]
    receipt["evidence_url"] = "http://localhost:8000/fake"
    with pytest.raises(GateError, match="HTTPS"):
        validate(state)
    receipt["evidence_url"] = "https://example.org/fake"
    receipt["artifact_sha256"] = "invalid"
    with pytest.raises(GateError, match="SHA-256"):
        validate(state)
    receipt["artifact_sha256"] = "b" * 64
    receipt["observed_at"] = (datetime.now(UTC) + timedelta(days=2)).isoformat()
    with pytest.raises(GateError, match="not future"):
        validate(state)


def test_four_wave_approval_is_required_for_entire_product() -> None:
    state = certified()
    state["waves"][3]["status"] = "blocked"
    with pytest.raises(GateError, match="all four waves"):
        validate(state, ready=True, release_sha=SHA)
