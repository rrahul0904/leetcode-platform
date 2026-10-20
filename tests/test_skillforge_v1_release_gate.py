from __future__ import annotations

import copy
import json
from pathlib import Path
from runpy import run_path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
release_gate = SimpleNamespace(
    **run_path(
        str(ROOT / "scripts" / "skillforge_v1_release_gate.py"),
        run_name="release_gate_test",
    )
)
BASELINE = ROOT / "docs/release/skillforge_v1_gate_status.json"
SHA = "a" * 40
RUN = "https://github.com/rrahul0904/leetcode-platform/actions/runs/39309131977"


def baseline() -> dict:
    return json.loads(BASELINE.read_text(encoding="utf-8"))


def verified(sha: str = SHA, *, deployment: bool = False) -> dict:
    evidence = {
        "sha": sha,
        "run_url": RUN,
        "observed_at_utc": "2026-10-19T19:30:00Z",
        "reviewed_by": "independent-reviewer",
    }
    if deployment:
        evidence["deployment_id"] = "dpl_Verified123"
    return {"status": "verified", "evidence": evidence}


def test_baseline_valid_and_truthfully_blocked() -> None:
    doc = release_gate.validate_document(baseline())
    approved, blocked = release_gate.release_progress(doc)
    assert approved == []
    assert blocked == [name for name, _ in release_gate.GATES]
    assert doc["release_sha"] is None


def test_all_gates_can_be_documented_at_one_sha() -> None:
    doc = baseline()
    doc["release_sha"] = SHA
    for name, _ in release_gate.GATES:
        doc["gates"][name] = verified(
            deployment=name in {
                "preview_identity", "preview_http", "staged_production",
                "production_postpromotion",
            }
        )
    result = release_gate.validate_document(doc)
    assert release_gate.release_progress(result)[1] == []


def test_first_gate_may_be_verified_while_rest_remains_blocked() -> None:
    doc = baseline()
    doc["release_sha"] = SHA
    doc["gates"]["source_ci"] = verified()
    assert release_gate.release_progress(release_gate.validate_document(doc))[0] == ["source_ci"]


@pytest.mark.parametrize("mutator", [
    lambda d: d.update({"repository": "attacker/untrusted"}),
    lambda d: d.update({"vercel_project_id": "prj_wrong"}),
    lambda d: d.update({"schema_version": 99}),
    lambda d: d.update({"release_sha": "short"}),
    lambda d: d["gates"].pop("source_ci"),
    lambda d: d["gates"]["source_ci"].update({"status": "complete"}),
    lambda d: d["gates"]["source_ci"].pop("reason"),
    lambda d: d["gates"]["source_ci"].update({"unsupported": "extra"}),
])
def test_rejects_invalid_contract(mutator) -> None:
    doc = baseline()
    mutator(doc)
    with pytest.raises(release_gate.ContractError):
        release_gate.validate_document(doc)


def test_cannot_skip_blocked_dependency() -> None:
    doc = baseline()
    doc["release_sha"] = SHA
    doc["gates"]["preview_identity"] = verified(deployment=True)
    with pytest.raises(release_gate.ContractError, match="earlier dependency"):
        release_gate.validate_document(doc)


def test_verified_gate_must_have_release_sha() -> None:
    doc = baseline()
    doc["gates"]["source_ci"] = verified()
    with pytest.raises(release_gate.ContractError, match="requires release_sha"):
        release_gate.validate_document(doc)


def test_rejects_wrong_evidence_commit() -> None:
    doc = baseline()
    doc["release_sha"] = SHA
    doc["gates"]["source_ci"] = verified("b" * 40)
    with pytest.raises(release_gate.ContractError, match="does not match"):
        release_gate.validate_document(doc)


@pytest.mark.parametrize("bad_url", [
    "http://github.com/rrahul0904/leetcode-platform/actions/runs/12",
    "https://github.com.evil.org/rrahul0904/leetcode-platform/actions/runs/12",
    "https://github.com/other/repo/actions/runs/12",
    "https://github.com/rrahul0904/leetcode-platform/pull/54",
    "https://github.com/rrahul0904/leetcode-platform/actions/runs/12?token=secret",
])
def test_rejects_untrusted_or_non_run_evidence(bad_url: str) -> None:
    doc = baseline()
    doc["release_sha"] = SHA
    doc["gates"]["source_ci"] = verified()
    doc["gates"]["source_ci"]["evidence"]["run_url"] = bad_url
    with pytest.raises(release_gate.ContractError, match="GitHub Actions"):
        release_gate.validate_document(doc)


def test_deployment_gates_require_exact_deployment_identifier() -> None:
    doc = baseline()
    doc["release_sha"] = SHA
    doc["gates"]["source_ci"] = verified()
    doc["gates"]["preview_identity"] = verified()
    with pytest.raises(release_gate.ContractError, match="evidence keys"):
        release_gate.validate_document(doc)


def test_utc_receipt_is_required() -> None:
    doc = baseline()
    doc["release_sha"] = SHA
    doc["gates"]["source_ci"] = verified()
    doc["gates"]["source_ci"]["evidence"]["observed_at_utc"] = "2026-10-19"
    with pytest.raises(release_gate.ContractError, match="UTC"):
        release_gate.validate_document(doc)


def test_baseline_cannot_be_claimed_release_ready(capsys: pytest.CaptureFixture[str]) -> None:
    assert release_gate.main(["--file", str(BASELINE), "--validate"]) == 0
    assert release_gate.main(["--file", str(BASELINE), "--report"]) == 0
    assert release_gate.main(["--file", str(BASELINE), "--assert-pre-release"]) == 1
    assert release_gate.main(["--file", str(BASELINE), "--assert-complete"]) == 1
    captured = capsys.readouterr()
    assert "RELEASE_BLOCKED" in captured.err
    assert '"state": "BLOCKED"' in captured.out


def test_wrong_canonical_project_will_never_pass() -> None:
    doc = baseline()
    assert doc["vercel_project_id"] == release_gate.VERCEL_PROJECT_ID
    other = copy.deepcopy(doc)
    other["vercel_project_id"] = "prj_duplicate"
    with pytest.raises(release_gate.ContractError):
        release_gate.validate_document(other)
