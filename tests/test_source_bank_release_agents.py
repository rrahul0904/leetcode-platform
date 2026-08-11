from __future__ import annotations

import json
import zipfile
from pathlib import Path

from scripts.source_bank_release_agents import (
    BLOCKED,
    FAIL,
    PASS,
    AgentContext,
    AgentResult,
    _overall,
    _valid_approval,
    _validate_run_submit_proof,
    compare_archive_fingerprint,
    corpus_agent,
    fingerprint_source_archive,
    provenance_agent,
)

ROOT = Path(__file__).resolve().parents[1]
LOCK = ROOT / "content" / "imported" / "source-backed" / "source-lock.json"


def _context(tmp_path: Path, **overrides: object) -> AgentContext:
    values: dict[str, object] = {
        "lock_path": LOCK,
        "work": tmp_path / "work",
        "source_archive_dir": None,
        "reviewed_corpus": None,
        "database_url": None,
        "approval_file": None,
        "run_submit_proof": None,
        "install": False,
        "install_target": tmp_path / "installed.b64",
    }
    values.update(overrides)
    return AgentContext(**values)  # type: ignore[arg-type]


def test_source_archive_fingerprint_detects_language_license_and_shape(
    tmp_path: Path,
) -> None:
    archive = tmp_path / "source.zip"
    with zipfile.ZipFile(archive, "w") as bundle:
        bundle.writestr("LeetCode-Solutions-master/", "")
        bundle.writestr(
            "LeetCode-Solutions-master/LICENSE",
            (
                "Permission is hereby granted, free of charge, to any person "
                "obtaining a copy of this software."
            ),
        )
        bundle.writestr(
            "LeetCode-Solutions-master/README.md",
            "| Topic | Difficulty | Time Complexity | Space Complexity | Solution |",
        )
        bundle.writestr("LeetCode-Solutions-master/a.js", "function a() {}")
        bundle.writestr("LeetCode-Solutions-master/b.js", "function b() {}")

    fingerprint = fingerprint_source_archive(archive)

    assert fingerprint["raw_zip_entries"] == 5
    assert fingerprint["useful_javascript_files"] == 2
    assert fingerprint["license"] == "MIT"
    assert fingerprint["readme_catalog_shape"] is True
    assert (
        compare_archive_fingerprint(
            fingerprint,
            {
                "raw_zip_entries": 5,
                "useful_code_files": 2,
                "license": "MIT",
                "readme_shape": "catalog signature",
            },
        )
        == []
    )


def test_compare_archive_fingerprint_rejects_near_match(tmp_path: Path) -> None:
    archive = tmp_path / "source.zip"
    with zipfile.ZipFile(archive, "w") as bundle:
        bundle.writestr("root/a.js", "function a() {}")

    fingerprint = fingerprint_source_archive(archive)
    mismatches = compare_archive_fingerprint(
        fingerprint,
        {"raw_zip_entries": 288, "useful_files": 222, "useful_code_files": 210},
    )

    assert any("raw_zip_entries" in item for item in mismatches)
    assert any("useful_files" in item for item in mismatches)
    assert any("useful_code_files" in item for item in mismatches)


def test_current_source_lock_stays_blocked_without_missing_artifacts(
    tmp_path: Path,
) -> None:
    result = provenance_agent(_context(tmp_path))

    assert result.status == BLOCKED
    assert result.evidence["release_grade_or_supplied_sources"] == 9
    assert result.evidence["required_sources"] == 11
    assert any("LeetCode-Solutions-master.zip" in item for item in result.blockers)
    assert any("Competitive-Programming-master.zip" in item for item in result.blockers)


def test_corpus_agent_rejects_wrong_reviewed_sha(tmp_path: Path) -> None:
    fake = tmp_path / "fake.zip"
    with zipfile.ZipFile(fake, "w") as bundle:
        bundle.writestr("manifest.json", "{}")

    provenance = AgentResult(
        agent="provenance",
        status=PASS,
        summary="ready",
        blockers=[],
        evidence={},
        outputs={},
    )
    result = corpus_agent(
        _context(tmp_path, reviewed_corpus=fake),
        provenance,
    )

    assert result.status == FAIL
    assert result.blockers == ["reviewed_corpus_sha_mismatch"]


def test_approval_contract_requires_explicit_governance_evidence() -> None:
    valid = {
        "package_id": "IMP-0007",
        "rights_disposition": "hostable_licensed",
        "publication_approved": True,
        "approved_by": "content-governance-reviewer",
        "approved_at": "2026-08-11T00:00:00Z",
        "license_identifier": "MIT",
        "evidence": ["Reviewed source license and redistribution grant."],
        "modification_rights": True,
        "export_rights": True,
    }
    assert _valid_approval(valid) == []

    invalid = dict(valid)
    invalid["publication_approved"] = False
    invalid["evidence"] = []
    problems = _valid_approval(invalid)
    assert "publication_approved must be true" in problems
    assert "evidence must contain at least one non-empty item" in problems


def test_run_submit_proof_requires_run_submit_hidden_and_idempotency(
    tmp_path: Path,
) -> None:
    proof = tmp_path / "proof.json"
    proof.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "package_id": "IMP-0007",
                "run": {
                    "status": "COMPLETED",
                    "public_tests_passed": True,
                },
                "submit": {
                    "status": "COMPLETED",
                    "hidden_total": 4,
                    "hidden_passed": 4,
                },
                "idempotency": {
                    "run_duplicate": True,
                    "submit_duplicate": True,
                },
            }
        ),
        encoding="utf-8",
    )

    valid, _, blockers = _validate_run_submit_proof(
        proof,
        executable_packages=["IMP-0007"],
    )
    assert valid is True
    assert blockers == []

    data = json.loads(proof.read_text(encoding="utf-8"))
    data["submit"]["hidden_passed"] = 3
    proof.write_text(json.dumps(data), encoding="utf-8")
    valid, _, blockers = _validate_run_submit_proof(
        proof,
        executable_packages=["IMP-0007"],
    )
    assert valid is False
    assert "Submit proof hidden tests did not all pass" in blockers


def test_overall_status_is_fail_closed() -> None:
    passed = AgentResult("a", PASS, "", [], {}, {})
    blocked = AgentResult("b", BLOCKED, "", [], {}, {})
    failed = AgentResult("c", FAIL, "", [], {}, {})

    assert _overall({"a": passed}) == PASS
    assert _overall({"a": passed, "b": blocked}) == BLOCKED
    assert _overall({"a": passed, "b": blocked, "c": failed}) == FAIL
