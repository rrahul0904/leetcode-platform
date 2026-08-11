#!/usr/bin/env python3
"""Multi-agent source-bank release coordinator.

Each agent owns one release concern and emits machine-readable evidence:
- provenance: 11/11 source identity/content evidence
- corpus: exact reviewed 3,425-question normalized archive
- database: clean import + repeat-import idempotency
- rights: explicit source-backed publication/governance approval
- run-submit: source-backed executable promotion/readiness boundary

The coordinator is deliberately fail-closed. Missing external evidence is BLOCKED,
not inferred, substituted, or silently approved.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import shutil
import subprocess
import sys
import zipfile
from collections.abc import Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath
from typing import cast

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIRECTORY = ROOT / "scripts"
scripts_path = str(SCRIPTS_DIRECTORY)
if scripts_path not in sys.path:
    sys.path.insert(0, scripts_path)

try:
    from fingerprint_source_repository import (
        BUILDER_CODE_EXTENSIONS,
        LANGUAGE_EXTENSIONS,
        LICENSE_BASENAME_PREFIXES,
        PROVENANCE_BASENAMES,
        PROVENANCE_TEXT_EXTENSIONS,
        _infer_license,
    )
    from import_source_backed_question_bank import load_payload, validate_payload
    from install_source_python_packages import (
        EXPECTED_PACKAGE_IDS,
        install_packages,
    )
    from rebuild_source_backed_question_bank import (
        RELEASE_GRADE_RESOLUTIONS,
        _archive_source,
        _object,
        build_corpus,
        install_bundle,
        load_source_lock,
        validate_manifest,
        write_deterministic_bundle,
    )
    from verify_source_bank_release import verify_release
except ModuleNotFoundError:
    from scripts.fingerprint_source_repository import (
        BUILDER_CODE_EXTENSIONS,
        LANGUAGE_EXTENSIONS,
        LICENSE_BASENAME_PREFIXES,
        PROVENANCE_BASENAMES,
        PROVENANCE_TEXT_EXTENSIONS,
        _infer_license,
    )
    from scripts.import_source_backed_question_bank import load_payload, validate_payload
    from scripts.install_source_python_packages import (
        EXPECTED_PACKAGE_IDS,
        install_packages,
    )
    from scripts.rebuild_source_backed_question_bank import (
        RELEASE_GRADE_RESOLUTIONS,
        _archive_source,
        _object,
        build_corpus,
        install_bundle,
        load_source_lock,
        validate_manifest,
        write_deterministic_bundle,
    )
    from scripts.verify_source_bank_release import verify_release

SOURCE_DIRECTORY = ROOT / "content" / "imported" / "source-backed"
DEFAULT_LOCK = SOURCE_DIRECTORY / "source-lock.json"
DEFAULT_WORK = ROOT / ".work" / "source-bank-release-agents"
DEFAULT_INSTALL_TARGET = SOURCE_DIRECTORY / "question-bank.zip.b64"
EXPECTED_ARCHIVES = 11
EXPECTED_PYTHON_FINGERPRINTS = 20

PASS = "PASS"
BLOCKED = "BLOCKED"
FAIL = "FAIL"


@dataclass(frozen=True)
class AgentResult:
    agent: str
    status: str
    summary: str
    blockers: list[str]
    evidence: dict[str, object]
    outputs: dict[str, str]

    def render(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class AgentContext:
    lock_path: Path
    work: Path
    source_archive_dir: Path | None
    reviewed_corpus: Path | None
    database_url: str | None
    approval_file: Path | None
    run_submit_proof: Path | None
    install: bool
    install_target: Path


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _safe_json(path: Path) -> dict[str, object]:
    value: object = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return {str(key): item for key, item in cast(dict[object, object], value).items()}


def _is_useful_path(path: str) -> bool:
    item = PurePosixPath(path)
    suffix = item.suffix.casefold()
    name = item.name.casefold()
    stem = item.stem.casefold()
    if suffix in PROVENANCE_TEXT_EXTENSIONS:
        return True
    if name in PROVENANCE_BASENAMES or stem in PROVENANCE_BASENAMES:
        return True
    return name.startswith(LICENSE_BASENAME_PREFIXES)


def _is_license_path(path: str) -> bool:
    return PurePosixPath(path).name.casefold().startswith(LICENSE_BASENAME_PREFIXES)


def _read_text_member(bundle: zipfile.ZipFile, name: str) -> str:
    try:
        raw = bundle.read(name)
    except (KeyError, RuntimeError, zipfile.BadZipFile):
        return ""
    if len(raw) > 2_000_000:
        return ""
    return raw.decode("utf-8", errors="replace")


def fingerprint_source_archive(path: Path) -> dict[str, object]:
    """Return the builder-relevant fingerprint for an original source ZIP."""

    with zipfile.ZipFile(path) as bundle:
        entries = bundle.infolist()
        files = [item for item in entries if not item.is_dir()]
        useful = sum(_is_useful_path(item.filename) for item in files)
        code = sum(
            PurePosixPath(item.filename).suffix.casefold() in BUILDER_CODE_EXTENSIONS
            for item in files
        )
        javascript = sum(
            PurePosixPath(item.filename).suffix.casefold()
            in LANGUAGE_EXTENSIONS["javascript"]
            for item in files
        )
        cpp = sum(
            PurePosixPath(item.filename).suffix.casefold()
            in LANGUAGE_EXTENSIONS["cpp"]
            for item in files
        )

        detected_license: str | None = None
        for item in files:
            if not _is_license_path(item.filename):
                continue
            detected_license = _infer_license(_read_text_member(bundle, item.filename))
            if detected_license:
                break

        readme_text = ""
        for item in files:
            name = PurePosixPath(item.filename).name.casefold()
            if name == "readme" or PurePosixPath(item.filename).stem.casefold() == "readme":
                readme_text = _read_text_member(bundle, item.filename)
                if readme_text:
                    break
        readme_normalized = " ".join(readme_text.casefold().split())
        catalog_shape = all(
            token in readme_normalized
            for token in ("topic", "difficulty", "time", "space", "solution")
        )

    payload = path.read_bytes()
    return {
        "archive": str(path),
        "archive_sha256": _sha256(payload),
        "archive_bytes": len(payload),
        "raw_zip_entries": len(entries),
        "useful_files": useful,
        "useful_code_files": code,
        "useful_javascript_files": javascript,
        "useful_cpp_files": cpp,
        "license": detected_license,
        "readme_catalog_shape": catalog_shape,
    }


def compare_archive_fingerprint(
    observed: Mapping[str, object],
    expected: Mapping[str, object],
) -> list[str]:
    key_map = {
        "raw_zip_entries": "raw_zip_entries",
        "useful_files": "useful_files",
        "useful_code_files": "useful_code_files",
        "useful_cpp_files": "useful_cpp_files",
        "license": "license",
    }
    mismatches: list[str] = []
    for expected_key, observed_key in key_map.items():
        if expected_key not in expected:
            continue
        wanted = expected[expected_key]
        actual = observed.get(observed_key)
        if actual != wanted:
            mismatches.append(f"{expected_key}: expected {wanted!r}, found {actual!r}")
    if "readme_shape" in expected and observed.get("readme_catalog_shape") is not True:
        mismatches.append("readme_shape: reviewed catalog signature not reproduced")
    return mismatches


def provenance_agent(context: AgentContext) -> AgentResult:
    lock = load_source_lock(context.lock_path)
    if lock.get("schema_version") != 1:
        return AgentResult(
            "provenance",
            FAIL,
            "Source lock schema is unsupported.",
            ["source_lock_schema_invalid"],
            {"schema_version": lock.get("schema_version")},
            {},
        )

    raw_sources = lock.get("sources")
    if not isinstance(raw_sources, list) or len(raw_sources) != EXPECTED_ARCHIVES:
        return AgentResult(
            "provenance",
            FAIL,
            "Source lock no longer contains the immutable 11-archive contract.",
            ["source_lock_archive_count_invalid"],
            {"archives": len(raw_sources) if isinstance(raw_sources, list) else None},
            {},
        )

    source_results: list[dict[str, object]] = []
    blockers: list[str] = []
    artifact_sources: dict[str, str] = {}
    ready = 0

    for index, raw in enumerate(raw_sources):
        source = _object(raw, label=f"sources[{index}]")
        name = str(source.get("archive_name") or "")
        resolution = str(source.get("resolution") or "")
        duplicate_of = source.get("duplicate_of")

        if duplicate_of is not None:
            ready += 1
            source_results.append(
                {
                    "archive_name": name,
                    "status": PASS,
                    "resolution": "exact_duplicate",
                    "duplicate_of": str(duplicate_of),
                }
            )
            continue

        repository = str(source.get("repository") or "")
        commit = str(source.get("commit") or "")
        if (
            resolution in RELEASE_GRADE_RESOLUTIONS
            and repository.startswith("https://github.com/")
            and len(commit) == 40
        ):
            ready += 1
            source_results.append(
                {
                    "archive_name": name,
                    "status": PASS,
                    "resolution": resolution,
                    "repository": repository,
                    "commit": commit,
                }
            )
            continue

        artifact = (
            context.source_archive_dir / name
            if context.source_archive_dir is not None
            else None
        )
        if artifact is None or not artifact.is_file():
            blockers.append(f"{name}: exact source artifact is unavailable")
            source_results.append(
                {
                    "archive_name": name,
                    "status": BLOCKED,
                    "resolution": resolution or "unresolved",
                    "artifact": str(artifact) if artifact else None,
                }
            )
            continue

        try:
            observed = fingerprint_source_archive(artifact)
        except (OSError, zipfile.BadZipFile, ValueError) as exc:
            blockers.append(f"{name}: supplied source artifact is invalid: {exc}")
            source_results.append(
                {
                    "archive_name": name,
                    "status": FAIL,
                    "resolution": "artifact_invalid",
                    "artifact": str(artifact),
                    "error": str(exc),
                }
            )
            continue

        expected = _object(
            source.get("expected_fingerprint"),
            label=f"{name}.expected_fingerprint",
        )
        mismatches = compare_archive_fingerprint(observed, expected)
        if mismatches:
            blockers.extend(f"{name}: {item}" for item in mismatches)
            source_results.append(
                {
                    "archive_name": name,
                    "status": FAIL,
                    "resolution": "artifact_fingerprint_mismatch",
                    "artifact": str(artifact),
                    "observed": observed,
                    "mismatches": mismatches,
                }
            )
            continue

        ready += 1
        artifact_sources[name] = str(artifact)
        source_results.append(
            {
                "archive_name": name,
                "status": PASS,
                "resolution": "exact_original_artifact_verified",
                "artifact": str(artifact),
                "observed": observed,
            }
        )

    status = PASS if ready == EXPECTED_ARCHIVES and not blockers else BLOCKED
    if any(item.get("status") == FAIL for item in source_results):
        status = FAIL
    return AgentResult(
        "provenance",
        status,
        f"{ready}/{EXPECTED_ARCHIVES} source archives have effective release evidence.",
        blockers,
        {
            "release_grade_or_supplied_sources": ready,
            "required_sources": EXPECTED_ARCHIVES,
            "sources": source_results,
            "source_lock_release_grade": sum(
                1
                for item in source_results
                if item.get("resolution")
                in RELEASE_GRADE_RESOLUTIONS | {"exact_duplicate"}
            ),
        },
        artifact_sources,
    )


def _decode_reviewed_corpus(path: Path) -> bytes:
    data = path.read_bytes()
    if path.suffix.casefold() in {".b64", ".base64"}:
        return base64.b64decode(b"".join(data.split()), validate=True)
    if data.startswith(b"PK\x03\x04"):
        return data
    try:
        decoded = base64.b64decode(b"".join(data.split()), validate=True)
    except Exception:
        return data
    return decoded if decoded.startswith(b"PK\x03\x04") else data


def _write_b64_archive(payload: bytes, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        base64.b64encode(payload).decode("ascii") + "\n",
        encoding="ascii",
    )


def _materialize_effective_archives(
    context: AgentContext,
    provenance: AgentResult,
    *,
    sources: Sequence[Mapping[str, object]],
) -> list[Path]:
    archive_root = context.work / "corpus" / "archives"
    cache_root = context.work / "corpus" / "repos"
    archive_root.mkdir(parents=True, exist_ok=True)
    generated: dict[str, Path] = {}
    pending_duplicates: list[Mapping[str, object]] = []

    for source in sources:
        name = str(source["archive_name"])
        if source.get("duplicate_of") is not None:
            pending_duplicates.append(source)
            continue

        repository = str(source.get("repository") or "")
        commit = str(source.get("commit") or "")
        resolution = str(source.get("resolution") or "")
        if (
            resolution in RELEASE_GRADE_RESOLUTIONS
            and repository.startswith("https://github.com/")
            and len(commit) == 40
        ):
            generated[name] = _archive_source(
                source,
                cache_root=cache_root,
                archive_root=archive_root,
            )
            continue

        supplied = provenance.outputs.get(name)
        if not supplied:
            raise RuntimeError(
                f"{name}: provenance agent did not provide an exact source artifact"
            )
        source_path = Path(supplied)
        destination = archive_root / name
        shutil.copyfile(source_path, destination)
        generated[name] = destination

    for source in pending_duplicates:
        name = str(source["archive_name"])
        original_name = str(source["duplicate_of"])
        original = generated.get(original_name)
        if original is None:
            raise RuntimeError(
                f"{name}: duplicate source {original_name} is unavailable"
            )
        destination = archive_root / name
        shutil.copyfile(original, destination)
        generated[name] = destination

    return [generated[str(source["archive_name"])] for source in sources]


def corpus_agent(context: AgentContext, provenance: AgentResult) -> AgentResult:
    lock = load_source_lock(context.lock_path)
    expected_sha = str(lock.get("reviewed_normalized_archive_sha256") or "")
    expected_manifest = _object(lock.get("expected_manifest"), label="expected_manifest")
    agent_root = context.work / "corpus"
    b64_path = agent_root / "question-bank.zip.b64"
    raw_path = agent_root / "rigor_source_backed_question_bank.zip"

    try:
        if context.reviewed_corpus is not None:
            if not context.reviewed_corpus.is_file():
                return AgentResult(
                    "corpus",
                    BLOCKED,
                    "Reviewed corpus path was supplied but does not exist.",
                    ["reviewed_corpus_missing"],
                    {"path": str(context.reviewed_corpus)},
                    {},
                )
            payload = _decode_reviewed_corpus(context.reviewed_corpus)
            actual_sha = _sha256(payload)
            if actual_sha != expected_sha:
                return AgentResult(
                    "corpus",
                    FAIL,
                    "Supplied reviewed corpus does not match the immutable reviewed SHA.",
                    ["reviewed_corpus_sha_mismatch"],
                    {"expected_sha256": expected_sha, "actual_sha256": actual_sha},
                    {},
                )
            agent_root.mkdir(parents=True, exist_ok=True)
            raw_path.write_bytes(payload)
            _write_b64_archive(payload, b64_path)
            payload_object = load_payload(b64_path)
            payload_counts = validate_payload(payload_object)
            if context.install:
                _write_b64_archive(payload, context.install_target)
            return AgentResult(
                "corpus",
                PASS,
                "Exact reviewed normalized corpus was supplied and verified.",
                [],
                {
                    "route": "exact_reviewed_corpus",
                    "sha256": actual_sha,
                    "payload_counts": payload_counts,
                },
                {"archive": str(raw_path), "archive_b64": str(b64_path)},
            )

        if provenance.status != PASS:
            return AgentResult(
                "corpus",
                BLOCKED,
                (
                    "Deterministic corpus reconstruction is waiting on effective "
                    "11/11 provenance."
                ),
                ["provenance_not_ready"],
                {
                    "provenance_status": provenance.status,
                    "reviewed_sha256": expected_sha,
                },
                {},
            )

        raw_sources = lock.get("sources")
        if not isinstance(raw_sources, list):
            raise ValueError("source lock sources must be a list")
        sources = [
            _object(item, label=f"sources[{index}]")
            for index, item in enumerate(raw_sources)
        ]
        archives = _materialize_effective_archives(
            context,
            provenance,
            sources=sources,
        )
        generated_root = agent_root / "generated"
        manifest = build_corpus(archives, output_root=generated_root)
        validate_manifest(manifest, expected_manifest)
        actual_sha = write_deterministic_bundle(generated_root, raw_path)
        if actual_sha != expected_sha:
            return AgentResult(
                "corpus",
                FAIL,
                "Reconstructed normalized corpus differs from the reviewed SHA.",
                ["reviewed_corpus_sha_mismatch"],
                {
                    "expected_sha256": expected_sha,
                    "actual_sha256": actual_sha,
                    "manifest": manifest,
                },
                {"archive": str(raw_path)},
            )
        install_bundle(raw_path, target=b64_path)
        if context.install:
            install_bundle(raw_path, target=context.install_target)
        payload_counts = validate_payload(load_payload(b64_path))
        return AgentResult(
            "corpus",
            PASS,
            "11-source reconstruction reproduced the exact reviewed normalized corpus.",
            [],
            {
                "route": "deterministic_reconstruction",
                "sha256": actual_sha,
                "manifest": manifest,
                "payload_counts": payload_counts,
            },
            {"archive": str(raw_path), "archive_b64": str(b64_path)},
        )
    except (
        OSError,
        RuntimeError,
        ValueError,
        subprocess.CalledProcessError,
        zipfile.BadZipFile,
    ) as exc:
        return AgentResult(
            "corpus",
            FAIL,
            "Corpus agent failed while validating or reconstructing the reviewed artifact.",
            ["corpus_agent_error"],
            {"error": str(exc), "expected_sha256": expected_sha},
            {},
        )


def database_agent(context: AgentContext, corpus: AgentResult) -> AgentResult:
    archive = corpus.outputs.get("archive_b64")
    if corpus.status != PASS or not archive:
        return AgentResult(
            "database",
            BLOCKED,
            "Database import/idempotency proof is waiting on the exact reviewed corpus.",
            ["corpus_not_ready"],
            {"corpus_status": corpus.status},
            {},
        )
    if not context.database_url:
        return AgentResult(
            "database",
            BLOCKED,
            "Exact corpus is available, but no clean PostgreSQL database URL was supplied.",
            ["database_url_missing"],
            {},
            {},
        )
    try:
        evidence = verify_release(Path(archive), context.database_url)
    except Exception as exc:
        return AgentResult(
            "database",
            FAIL,
            "PostgreSQL release verification failed.",
            ["database_release_verification_failed"],
            {"error": str(exc)},
            {},
        )
    return AgentResult(
        "database",
        PASS,
        (
            "Full database import, exact counts, duplicate checks, and "
            "repeat-import idempotency passed."
        ),
        [],
        evidence,
        {},
    )


def _approval_records(path: Path) -> list[dict[str, object]]:
    root = _safe_json(path)
    if root.get("schema_version") != 1:
        raise ValueError("approval file schema_version must be 1")
    raw = root.get("approvals")
    if not isinstance(raw, list):
        raise ValueError("approval file approvals must be a list")
    return [
        _object(item, label=f"approvals[{index}]")
        for index, item in enumerate(raw)
    ]


def _valid_approval(record: Mapping[str, object]) -> list[str]:
    problems: list[str] = []
    package_id = str(record.get("package_id") or "")
    if package_id not in EXPECTED_PACKAGE_IDS:
        problems.append("package_id is not one of the reviewed IMP-* packages")
    if str(record.get("rights_disposition") or "") != "hostable_licensed":
        problems.append("rights_disposition must be hostable_licensed")
    if record.get("publication_approved") is not True:
        problems.append("publication_approved must be true")
    for key in ("approved_by", "approved_at", "license_identifier"):
        if not str(record.get(key) or "").strip():
            problems.append(f"{key} is required")
    evidence = record.get("evidence")
    if not isinstance(evidence, list) or not any(
        str(item).strip() for item in evidence
    ):
        problems.append("evidence must contain at least one non-empty item")
    if record.get("modification_rights") is not True:
        problems.append("modification_rights must be true")
    if record.get("export_rights") is not True:
        problems.append("export_rights must be true")
    return problems


def rights_agent(context: AgentContext) -> AgentResult:
    materialized = context.work / "rights" / "materialized-python"
    try:
        installation = install_packages(output=materialized, force=True)
    except (OSError, ValueError) as exc:
        return AgentResult(
            "rights",
            FAIL,
            "Checksum-pinned source-backed Python packages could not be materialized.",
            ["source_python_packages_invalid"],
            {"error": str(exc)},
            {},
        )

    if context.approval_file is None:
        return AgentResult(
            "rights",
            BLOCKED,
            (
                "Source-backed Python fingerprints/packages are intact, but "
                "publication rights/governance evidence is absent."
            ),
            ["rights_governance_approval_missing"],
            {
                "python_fingerprints": EXPECTED_PYTHON_FINGERPRINTS,
                "packages": installation.get("packages"),
                "published": 0,
            },
            {"materialized_root": str(materialized)},
        )
    if not context.approval_file.is_file():
        return AgentResult(
            "rights",
            BLOCKED,
            "A governance approval path was supplied but does not exist.",
            ["approval_file_missing"],
            {"path": str(context.approval_file)},
            {"materialized_root": str(materialized)},
        )

    try:
        records = _approval_records(context.approval_file)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return AgentResult(
            "rights",
            FAIL,
            "Governance approval evidence is malformed.",
            ["approval_file_invalid"],
            {"error": str(exc)},
            {"materialized_root": str(materialized)},
        )

    approved: list[str] = []
    rejected: dict[str, list[str]] = {}
    for record in records:
        package_id = str(record.get("package_id") or "<missing>")
        problems = _valid_approval(record)
        if problems:
            rejected[package_id] = problems
        elif package_id not in approved:
            approved.append(package_id)

    if not approved:
        return AgentResult(
            "rights",
            BLOCKED if not rejected else FAIL,
            "No source-backed package has complete hostable publication approval.",
            ["no_approved_source_backed_package"],
            {
                "submitted_approvals": len(records),
                "rejected": rejected,
                "validation_note": (
                    "This agent validates evidence completeness; it does not invent "
                    "or independently grant legal rights."
                ),
            },
            {"materialized_root": str(materialized)},
        )

    return AgentResult(
        "rights",
        PASS,
        (
            f"{len(approved)} source-backed package(s) have complete external "
            "governance evidence."
        ),
        [],
        {
            "approved_packages": sorted(approved),
            "rejected": rejected,
            "validation_note": (
                "Approval records are treated as external governance evidence. "
                "The agent does not manufacture rights or approval."
            ),
        },
        {"materialized_root": str(materialized)},
    )


def _proof_object(
    proof: Mapping[str, object],
    key: str,
    blockers: list[str],
) -> dict[str, object]:
    raw = proof.get(key)
    if not isinstance(raw, dict):
        blockers.append(f"run_submit_proof.{key} must be an object")
        return {}
    return {
        str(item_key): item_value
        for item_key, item_value in cast(dict[object, object], raw).items()
    }


def _validate_run_submit_proof(
    proof_path: Path,
    *,
    executable_packages: Sequence[str],
) -> tuple[bool, dict[str, object], list[str]]:
    try:
        proof = _safe_json(proof_path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return False, {"error": str(exc)}, ["run_submit_proof_invalid"]

    blockers: list[str] = []
    if proof.get("schema_version") != 1:
        blockers.append("run_submit_proof.schema_version must be 1")

    package_id = str(proof.get("package_id") or "")
    if package_id not in executable_packages:
        blockers.append(
            "run_submit_proof.package_id is not an approved executable package"
        )

    run = _proof_object(proof, "run", blockers)
    submit = _proof_object(proof, "submit", blockers)
    idempotency = _proof_object(proof, "idempotency", blockers)

    if str(run.get("status") or "") != "COMPLETED":
        blockers.append("Run proof must complete successfully")
    if run.get("public_tests_passed") is not True:
        blockers.append("Run proof must pass public tests")
    if str(submit.get("status") or "") != "COMPLETED":
        blockers.append("Submit proof must complete successfully")

    hidden_total = submit.get("hidden_total")
    hidden_passed = submit.get("hidden_passed")
    if (
        not isinstance(hidden_total, int)
        or isinstance(hidden_total, bool)
        or hidden_total <= 0
    ):
        blockers.append("Submit proof must include at least one hidden test")
    elif hidden_passed != hidden_total:
        blockers.append("Submit proof hidden tests did not all pass")

    if idempotency.get("run_duplicate") is not True:
        blockers.append("Run idempotency duplicate proof is missing")
    if idempotency.get("submit_duplicate") is not True:
        blockers.append("Submit idempotency duplicate proof is missing")

    return not blockers, proof, blockers


def run_submit_agent(context: AgentContext, rights: AgentResult) -> AgentResult:
    if rights.status != PASS:
        return AgentResult(
            "run-submit",
            BLOCKED,
            "Source-backed Run → Submit remains behind the rights/governance gate.",
            ["rights_not_ready"],
            {"rights_status": rights.status},
            {},
        )

    approved_raw = rights.evidence.get("approved_packages")
    approved = (
        [str(item) for item in approved_raw]
        if isinstance(approved_raw, list)
        else []
    )
    materialized_root = rights.outputs.get("materialized_root")
    if not approved or not materialized_root:
        return AgentResult(
            "run-submit",
            FAIL,
            "Rights agent passed without an executable package selection.",
            ["approved_package_missing"],
            {},
            {},
        )

    package_root = Path(materialized_root)
    executable: list[str] = []
    failures: dict[str, str] = {}
    for package_id in approved:
        package = package_root / package_id
        reference_test = package / "test_reference.py"
        if not reference_test.is_file():
            failures[package_id] = "test_reference.py missing"
            continue
        try:
            subprocess.run(
                [sys.executable, "-m", "pytest", "-q", reference_test.name],
                cwd=package,
                check=True,
                capture_output=True,
                text=True,
                timeout=120,
            )
        except (subprocess.SubprocessError, OSError) as exc:
            failures[package_id] = str(exc)
        else:
            executable.append(package_id)

    if not executable:
        return AgentResult(
            "run-submit",
            FAIL,
            (
                "Approved source-backed packages did not pass their executable "
                "reference contract."
            ),
            ["approved_package_execution_failed"],
            {"failures": failures},
            {},
        )

    if context.run_submit_proof is None:
        return AgentResult(
            "run-submit",
            BLOCKED,
            (
                "Approved package reference execution passes, but an actual "
                "Run → Submit end-to-end proof has not been supplied."
            ),
            ["run_submit_e2e_proof_missing"],
            {
                "executable_approved_packages": executable,
                "api_contract": {
                    "run": "rigor_api.execution_api.queue_run",
                    "submit": "rigor_api.execution_api.queue_submit",
                },
            },
            {},
        )
    if not context.run_submit_proof.is_file():
        return AgentResult(
            "run-submit",
            BLOCKED,
            "Run → Submit proof path was supplied but does not exist.",
            ["run_submit_e2e_proof_missing"],
            {"path": str(context.run_submit_proof)},
            {},
        )

    valid, proof, proof_blockers = _validate_run_submit_proof(
        context.run_submit_proof,
        executable_packages=executable,
    )
    if not valid:
        return AgentResult(
            "run-submit",
            FAIL,
            "Run → Submit end-to-end proof does not satisfy the release contract.",
            proof_blockers,
            proof,
            {},
        )

    return AgentResult(
        "run-submit",
        PASS,
        "Approved source-backed Run → Submit proof passed, including idempotency.",
        [],
        {
            "executable_approved_packages": executable,
            "proof": proof,
            "api_contract": {
                "run": "rigor_api.execution_api.queue_run",
                "submit": "rigor_api.execution_api.queue_submit",
                "idempotency": "execution request hash + Idempotency-Key",
            },
        },
        {},
    )


def _write_result(root: Path, result: AgentResult) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / f"{result.agent}.json").write_text(
        json.dumps(result.render(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def run_all(context: AgentContext) -> dict[str, AgentResult]:
    context.work.mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(max_workers=2, thread_name_prefix="release-agent") as pool:
        provenance_future = pool.submit(provenance_agent, context)
        rights_future = pool.submit(rights_agent, context)
        provenance = provenance_future.result()
        rights = rights_future.result()

    _write_result(context.work, provenance)
    _write_result(context.work, rights)

    corpus = corpus_agent(context, provenance)
    _write_result(context.work, corpus)
    database = database_agent(context, corpus)
    _write_result(context.work, database)
    run_submit = run_submit_agent(context, rights)
    _write_result(context.work, run_submit)

    return {
        result.agent: result
        for result in (provenance, corpus, database, rights, run_submit)
    }


def _overall(results: Mapping[str, AgentResult]) -> str:
    statuses = {result.status for result in results.values()}
    if FAIL in statuses:
        return FAIL
    if BLOCKED in statuses:
        return BLOCKED
    return PASS


def _render_report(results: Mapping[str, AgentResult]) -> dict[str, object]:
    overall = _overall(results)
    blockers = [
        f"{name}: {blocker}"
        for name, result in results.items()
        for blocker in result.blockers
    ]
    return {
        "schema_version": 1,
        "overall_status": overall,
        "agents": {
            name: result.render()
            for name, result in sorted(results.items())
        },
        "blockers": blockers,
        "immutable_release_contract": {
            "reviewed_normalized_archive_sha256": (
                "9236110b4c4af1547455998e96f100ce5d2ba945bba1fd02d9194714a11a873b"
            ),
            "archives": 11,
            "searchable_questions": 3425,
            "company_questions": 3424,
            "company_associations": 35348,
            "statement_backed": 121,
            "reference_solutions": 120,
            "unique_solution_slugs": 1063,
            "system_design_resources": 29,
            "source_csv_rows": 92728,
            "python_fingerprints": 20,
        },
    }


def _print_summary(report: Mapping[str, object]) -> None:
    print(f"Source-bank multi-agent release status: {report['overall_status']}")
    agents = report.get("agents")
    if isinstance(agents, dict):
        for name, raw in sorted(agents.items()):
            item = cast(dict[str, object], raw)
            print(f"- {name}: {item.get('status')} — {item.get('summary')}")
    blockers = report.get("blockers")
    if isinstance(blockers, list) and blockers:
        print("Blockers:")
        for blocker in blockers:
            print(f"  - {blocker}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--lock", type=Path, default=DEFAULT_LOCK)
    parser.add_argument("--work", type=Path, default=DEFAULT_WORK)
    parser.add_argument(
        "--source-archive-dir",
        type=Path,
        help=(
            "Directory containing exact original ZIPs for unresolved "
            "source-lock entries."
        ),
    )
    parser.add_argument(
        "--reviewed-corpus",
        type=Path,
        help=(
            "Exact reviewed normalized ZIP or base64 archive; immutable SHA "
            "is enforced."
        ),
    )
    parser.add_argument(
        "--database-url",
        default=os.getenv("RIGOR_DATABASE_URL"),
        help="Clean PostgreSQL URL for full import/idempotency verification.",
    )
    parser.add_argument(
        "--approval-file",
        type=Path,
        help="External governance approval JSON for reviewed IMP-* packages.",
    )
    parser.add_argument(
        "--run-submit-proof",
        type=Path,
        help="JSON evidence from an actual approved source-backed Run → Submit E2E.",
    )
    parser.add_argument("--install", action="store_true")
    parser.add_argument("--install-target", type=Path, default=DEFAULT_INSTALL_TARGET)
    parser.add_argument(
        "--enforce-release",
        action="store_true",
        help="Exit non-zero if any agent is BLOCKED or FAIL.",
    )
    args = parser.parse_args()

    context = AgentContext(
        lock_path=args.lock,
        work=args.work,
        source_archive_dir=args.source_archive_dir,
        reviewed_corpus=args.reviewed_corpus,
        database_url=args.database_url,
        approval_file=args.approval_file,
        run_submit_proof=args.run_submit_proof,
        install=args.install,
        install_target=args.install_target,
    )
    results = run_all(context)
    report = _render_report(results)
    report_path = args.work / "report.json"
    report_path.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    _print_summary(report)
    print(f"Report: {report_path}")
    if args.enforce_release and report["overall_status"] != PASS:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
