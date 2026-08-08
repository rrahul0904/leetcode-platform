from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts import rebuild_source_backed_question_bank as rebuild

EXPECTED_MANIFEST = {
    "archives": 11,
    "unique_company_index_questions": 3424,
    "statement_backed_hosted_candidates": 121,
    "hosted_candidates_with_reference_solution": 120,
    "system_design_resources": 29,
    "unique_solution_slugs": 1063,
    "company_mentions": 35348,
    "source_csv_rows_after_dedup": 92728,
}


def test_source_lock_preserves_reviewed_manifest_contract() -> None:
    lock = rebuild.load_source_lock()

    assert lock["expected_manifest"] == EXPECTED_MANIFEST
    assert lock["reviewed_normalized_archive_sha256"] == (
        "9236110b4c4af1547455998e96f100ce5d2ba945bba1fd02d9194714a11a873b"
    )
    assert len(lock["sources"]) == 11


def test_release_validation_fails_closed_while_sources_are_unresolved() -> None:
    lock = rebuild.load_source_lock()
    unresolved = {
        source["archive_name"]
        for source in lock["sources"]
        if source.get("resolution") == "unresolved"
    }
    assert unresolved

    with pytest.raises(rebuild.SourceLockError) as error:
        rebuild.validate_source_lock(lock)

    message = str(error.value)
    for archive_name in unresolved:
        assert archive_name in message
    assert "unresolved" in message


def test_output_fingerprint_is_diagnostic_only() -> None:
    lock = rebuild.load_source_lock()
    sources: list[dict[str, object]] = []

    for index, original in enumerate(lock["sources"]):
        source = dict(original)
        if source.get("resolution") == "unresolved":
            source["repository"] = f"https://github.com/example/recovered-source-{index}.git"
            source["commit"] = f"{index + 1:040x}"
            source["archive_root"] = f"recovered-source-{index}-master"
            source["resolution"] = "exact_source_verified"
        sources.append(source)

    diagnostic_index = next(
        index
        for index, source in enumerate(sources)
        if not source.get("duplicate_of")
        and source.get("repository")
        and source.get("commit")
    )
    diagnostic = dict(sources[diagnostic_index])
    diagnostic["resolution"] = "output_fingerprint_verified"
    sources[diagnostic_index] = diagnostic

    changed = dict(lock)
    changed["sources"] = sources

    with pytest.raises(rebuild.SourceLockError, match="output_fingerprint_verified"):
        rebuild.validate_source_lock(changed)

    validated = rebuild.validate_source_lock(
        changed,
        require_release_ready=False,
    )
    assert len(validated) == 11
    assert "output_fingerprint_verified" not in rebuild.RELEASE_GRADE_RESOLUTIONS


def test_duplicate_source_must_reference_an_existing_archive() -> None:
    lock = rebuild.load_source_lock()
    sources = list(lock["sources"])
    duplicate_index = next(
        index for index, source in enumerate(sources) if source.get("duplicate_of")
    )
    duplicate = dict(sources[duplicate_index])
    duplicate["duplicate_of"] = "missing-source.zip"
    sources[duplicate_index] = duplicate
    changed = dict(lock)
    changed["sources"] = sources

    with pytest.raises(rebuild.SourceLockError, match="duplicate_of target"):
        rebuild.validate_source_lock(changed, require_release_ready=False)


def test_manifest_validation_rejects_silent_count_drift() -> None:
    actual = dict(EXPECTED_MANIFEST)
    actual["company_mentions"] -= 1

    with pytest.raises(rebuild.SourceLockError, match="company_mentions"):
        rebuild.validate_manifest(actual, EXPECTED_MANIFEST)


def test_deterministic_bundle_is_byte_stable(tmp_path: Path) -> None:
    generated = tmp_path / "generated"
    generated.mkdir()
    for name in rebuild.REQUIRED_GENERATED_FILES:
        if name == "manifest.json":
            payload = json.dumps(EXPECTED_MANIFEST, sort_keys=True) + "\n"
        else:
            payload = f"{name}\n"
        (generated / name).write_text(payload, encoding="utf-8")

    first = tmp_path / "first.zip"
    second = tmp_path / "second.zip"
    first_sha = rebuild.write_deterministic_bundle(generated, first)
    second_sha = rebuild.write_deterministic_bundle(generated, second)

    assert first.read_bytes() == second.read_bytes()
    assert first_sha == second_sha
