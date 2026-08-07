#!/usr/bin/env python3
"""Rebuild the reviewed source-backed question bank from pinned Git revisions.

The source lock deliberately distinguishes recovered evidence from release-grade
source resolution. The default command is fail closed: every non-duplicate
archive must have an exact, release-approved source resolution before network
access or corpus generation begins.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import re
import shutil
import subprocess
import sys
import zipfile
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import cast

ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIRECTORY = ROOT / "content" / "imported" / "source-backed"
DEFAULT_LOCK = SOURCE_DIRECTORY / "source-lock.json"
DEFAULT_WORK = ROOT / ".work" / "source-bank-rebuild"
DEFAULT_INSTALL_TARGET = SOURCE_DIRECTORY / "question-bank.zip.b64"
BUILDER = ROOT / "scripts" / "build_uploaded_question_bank.py"
SHA256_PATTERN = re.compile(r"^[0-9a-f]{40}$")
RELEASE_RESOLUTIONS = {
    "exact_source_verified",
    "exact_content_fingerprint_verified",
}
REQUIRED_GENERATED_FILES = (
    "external_question_index.jsonl",
    "hosted_question_candidates.jsonl",
    "system_design_resources.jsonl",
    "manifest.json",
)


class SourceLockError(ValueError):
    """Raised when the reconstruction lock is incomplete or inconsistent."""


def _object(value: object, *, label: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise SourceLockError(f"{label} must be a JSON object")
    return {str(key): item for key, item in cast(dict[object, object], value).items()}


def load_source_lock(path: Path = DEFAULT_LOCK) -> dict[str, object]:
    return _object(json.loads(path.read_text(encoding="utf-8")), label=str(path))


def validate_source_lock(
    lock: Mapping[str, object],
    *,
    require_release_ready: bool = True,
) -> list[dict[str, object]]:
    schema_version = lock.get("schema_version")
    if schema_version != 1:
        raise SourceLockError(f"unsupported source lock schema_version: {schema_version!r}")

    reviewed_sha = str(lock.get("reviewed_normalized_archive_sha256") or "")
    if not re.fullmatch(r"[0-9a-f]{64}", reviewed_sha):
        raise SourceLockError("reviewed_normalized_archive_sha256 must be 64 lowercase hex characters")

    expected_manifest = _object(lock.get("expected_manifest"), label="expected_manifest")
    if expected_manifest.get("archives") != 11:
        raise SourceLockError("expected_manifest.archives must remain 11")

    raw_sources = lock.get("sources")
    if not isinstance(raw_sources, list):
        raise SourceLockError("sources must be a JSON array")
    sources = [_object(item, label=f"sources[{index}]") for index, item in enumerate(raw_sources)]
    if len(sources) != 11:
        raise SourceLockError(f"source lock must contain 11 archive entries, found {len(sources)}")

    by_name: dict[str, dict[str, object]] = {}
    blockers: list[str] = []
    for source in sources:
        name = str(source.get("archive_name") or "")
        if not name.endswith(".zip"):
            raise SourceLockError(f"invalid archive_name: {name!r}")
        if name in by_name:
            raise SourceLockError(f"duplicate source-lock archive_name: {name}")
        by_name[name] = source

        resolution = str(source.get("resolution") or "")
        duplicate_of = source.get("duplicate_of")
        if duplicate_of is not None:
            if resolution != "exact_duplicate":
                raise SourceLockError(f"{name}: duplicate sources must use exact_duplicate resolution")
            continue

        repository = str(source.get("repository") or "")
        commit = str(source.get("commit") or "").casefold()
        archive_root = str(source.get("archive_root") or "")
        if not repository.startswith("https://github.com/") or not repository.endswith(".git"):
            blockers.append(f"{name}: repository is unresolved")
        if not SHA256_PATTERN.fullmatch(commit):
            blockers.append(f"{name}: exact 40-character commit is unresolved")
        if not archive_root:
            blockers.append(f"{name}: archive_root is unresolved")
        if require_release_ready and resolution not in RELEASE_RESOLUTIONS:
            blockers.append(f"{name}: resolution={resolution or 'missing'} is not release-grade")

    for name, source in by_name.items():
        duplicate_of = source.get("duplicate_of")
        if duplicate_of is not None and str(duplicate_of) not in by_name:
            raise SourceLockError(f"{name}: duplicate_of target {duplicate_of!r} is absent")

    if blockers:
        raise SourceLockError("source reconstruction is blocked:\n- " + "\n- ".join(sorted(set(blockers))))
    return sources


def _run(args: Sequence[str], *, cwd: Path | None = None) -> None:
    subprocess.run(list(args), cwd=cwd, check=True)


def _archive_source(source: Mapping[str, object], *, cache_root: Path, archive_root: Path) -> Path:
    name = str(source["archive_name"])
    repository = str(source["repository"])
    commit = str(source["commit"])
    prefix = str(source["archive_root"]).rstrip("/") + "/"
    cache = cache_root / hashlib.sha256(repository.encode("utf-8")).hexdigest()[:16]
    if not (cache / ".git").exists():
        _run(["git", "clone", "--quiet", "--filter=blob:none", "--no-checkout", repository, str(cache)])
    _run(["git", "fetch", "--quiet", "origin", commit], cwd=cache)
    _run(["git", "cat-file", "-e", f"{commit}^{{commit}}"], cwd=cache)

    destination = archive_root / name
    destination.parent.mkdir(parents=True, exist_ok=True)
    _run(
        [
            "git",
            "archive",
            "--format=zip",
            f"--prefix={prefix}",
            f"--output={destination.resolve()}",
            commit,
        ],
        cwd=cache,
    )
    return destination


def materialize_source_archives(
    sources: Sequence[Mapping[str, object]],
    *,
    cache_root: Path,
    archive_root: Path,
) -> list[Path]:
    archive_root.mkdir(parents=True, exist_ok=True)
    generated: dict[str, Path] = {}
    pending_duplicates: list[Mapping[str, object]] = []
    for source in sources:
        if source.get("duplicate_of") is not None:
            pending_duplicates.append(source)
            continue
        path = _archive_source(source, cache_root=cache_root, archive_root=archive_root)
        generated[str(source["archive_name"])] = path

    for source in pending_duplicates:
        name = str(source["archive_name"])
        original_name = str(source["duplicate_of"])
        original = generated.get(original_name)
        if original is None:
            raise SourceLockError(f"{name}: duplicate source {original_name} was not materialized")
        destination = archive_root / name
        shutil.copyfile(original, destination)
        generated[name] = destination
        if hashlib.sha256(original.read_bytes()).digest() != hashlib.sha256(destination.read_bytes()).digest():
            raise SourceLockError(f"{name}: duplicate archive bytes diverged from {original_name}")

    return [generated[str(source["archive_name"])] for source in sources]


def validate_manifest(actual: Mapping[str, object], expected: Mapping[str, object]) -> None:
    mismatches = []
    for key, expected_value in expected.items():
        actual_value = actual.get(key)
        if actual_value != expected_value:
            mismatches.append(f"{key}: expected {expected_value!r}, found {actual_value!r}")
    if mismatches:
        raise SourceLockError("rebuilt corpus manifest does not match the reviewed corpus:\n- " + "\n- ".join(mismatches))


def build_corpus(archives: Sequence[Path], *, output_root: Path) -> dict[str, object]:
    if output_root.exists():
        shutil.rmtree(output_root)
    output_root.mkdir(parents=True)
    _run([sys.executable, str(BUILDER), *(str(path) for path in archives), "--output", str(output_root)])
    manifest = _object(json.loads((output_root / "manifest.json").read_text(encoding="utf-8")), label="rebuilt manifest")
    missing = [name for name in REQUIRED_GENERATED_FILES if not (output_root / name).is_file()]
    if missing:
        raise SourceLockError(f"builder did not produce required files: {missing}")
    return manifest


def write_deterministic_bundle(output_root: Path, destination: Path) -> str:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(destination, mode="w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as bundle:
        for name in sorted(REQUIRED_GENERATED_FILES):
            payload = (output_root / name).read_bytes()
            info = zipfile.ZipInfo(filename=name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            info.create_system = 3
            bundle.writestr(info, payload, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    return hashlib.sha256(destination.read_bytes()).hexdigest()


def install_bundle(bundle: Path, *, target: Path) -> None:
    encoded = base64.b64encode(bundle.read_bytes()).decode("ascii")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(encoded + "\n", encoding="ascii")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--lock", type=Path, default=DEFAULT_LOCK)
    parser.add_argument("--work", type=Path, default=DEFAULT_WORK)
    parser.add_argument(
        "--allow-provisional",
        action="store_true",
        help="diagnostic only: allow non-release-grade source resolutions",
    )
    parser.add_argument(
        "--skip-reviewed-sha-check",
        action="store_true",
        help="diagnostic only: validate manifest but do not require the reviewed normalized ZIP SHA-256",
    )
    parser.add_argument("--install", action="store_true")
    parser.add_argument("--install-target", type=Path, default=DEFAULT_INSTALL_TARGET)
    args = parser.parse_args()

    lock = load_source_lock(args.lock)
    sources = validate_source_lock(lock, require_release_ready=not args.allow_provisional)
    expected_manifest = _object(lock["expected_manifest"], label="expected_manifest")
    expected_sha = str(lock["reviewed_normalized_archive_sha256"])

    cache_root = args.work / "repos"
    archive_root = args.work / "archives"
    generated_root = args.work / "generated"
    bundle_path = args.work / "rigor_source_backed_question_bank.zip"
    archive_root.mkdir(parents=True, exist_ok=True)

    archives = materialize_source_archives(sources, cache_root=cache_root, archive_root=archive_root)
    manifest = build_corpus(archives, output_root=generated_root)
    validate_manifest(manifest, expected_manifest)
    actual_sha = write_deterministic_bundle(generated_root, bundle_path)

    if not args.skip_reviewed_sha_check and actual_sha != expected_sha:
        raise SourceLockError(
            "rebuilt normalized archive SHA-256 differs from the reviewed archive: "
            f"expected {expected_sha}, found {actual_sha}"
        )
    if args.install:
        if args.skip_reviewed_sha_check:
            raise SourceLockError("refusing --install when --skip-reviewed-sha-check is enabled")
        install_bundle(bundle_path, target=args.install_target)

    print(json.dumps({"archive": str(bundle_path), "sha256": actual_sha, "manifest": manifest}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
