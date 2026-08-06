#!/usr/bin/env python3
"""Install checksum-pinned native Python question packages safely and idempotently."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import shutil
import tarfile
import tempfile
from pathlib import Path, PurePosixPath
from typing import BinaryIO

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DIRECTORY = ROOT / "content" / "imported" / "source-backed"
DEFAULT_OUTPUT = ROOT / "content" / "questions" / "python"
PART_GLOB = "python-packages.tar.xz.part[0-9][0-9]"
EXPECTED_PART_COUNT = 6
EXPECTED_ARCHIVE_SHA256 = (
    "bf7fccca8708e3e9b52f26e20cde3ccf39ff9ffd31130b067185434240150cc4"
)
EXPECTED_PACKAGE_IDS = (
    "IMP-0007",
    "IMP-0009",
    "IMP-0016",
    "IMP-0021",
    "IMP-0032",
    "IMP-0039",
    "IMP-0054",
    "IMP-0055",
    "IMP-0057",
    "IMP-0060",
    "IMP-0066",
    "IMP-0071",
    "IMP-0073",
    "IMP-0095",
    "IMP-0096",
    "IMP-0097",
    "IMP-0099",
    "IMP-0103",
    "IMP-0104",
    "IMP-0120",
)
REQUIRED_FILES = (
    "question.json",
    "rights.json",
    "rubric.json",
    "solution.json",
    "metadata.json",
    "reference.py",
    "test_reference.py",
    "tests/public.json",
    "tests/hidden.json",
)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def assemble_archive(
    directory: Path = DEFAULT_DIRECTORY,
    *,
    expected_part_count: int = EXPECTED_PART_COUNT,
    expected_sha256: str = EXPECTED_ARCHIVE_SHA256,
) -> bytes:
    parts = sorted(directory.glob(PART_GLOB))
    if len(parts) != expected_part_count:
        raise ValueError(
            f"expected {expected_part_count} package archive parts, found {len(parts)}"
        )
    archive = b"".join(path.read_bytes() for path in parts)
    actual = _sha256(archive)
    if actual != expected_sha256:
        raise ValueError(
            "native package archive checksum mismatch: "
            f"expected {expected_sha256}, found {actual}"
        )
    return archive


def _safe_relative_path(name: str) -> Path:
    pure = PurePosixPath(name)
    if pure.is_absolute() or not pure.parts or any(
        part in {"", ".", ".."} for part in pure.parts
    ):
        raise ValueError(f"unsafe archive member path: {name!r}")
    if pure.parts[0] not in EXPECTED_PACKAGE_IDS:
        raise ValueError(f"unexpected package in archive: {pure.parts[0]!r}")
    return Path(*pure.parts)


def _copy_member(source: BinaryIO, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("wb") as stream:
        shutil.copyfileobj(source, stream)


def extract_archive(archive: bytes, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    try:
        bundle = tarfile.open(fileobj=io.BytesIO(archive), mode="r:xz")
    except (tarfile.TarError, EOFError, OSError) as exc:
        raise ValueError("native package archive is not a valid xz-compressed tar") from exc
    with bundle:
        for member in bundle.getmembers():
            relative = _safe_relative_path(member.name)
            target = destination / relative
            if member.isdir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            if not member.isfile():
                raise ValueError(
                    "archive member must be a regular file or directory: "
                    f"{member.name!r}"
                )
            source = bundle.extractfile(member)
            if source is None:
                raise ValueError(f"could not read archive member: {member.name!r}")
            with source:
                _copy_member(source, target)


def _tree_digest(directory: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(item for item in directory.rglob("*") if item.is_file()):
        relative = path.relative_to(directory).as_posix().encode("utf-8")
        digest.update(len(relative).to_bytes(4, "big"))
        digest.update(relative)
        data = path.read_bytes()
        digest.update(len(data).to_bytes(8, "big"))
        digest.update(data)
    return digest.hexdigest()


def verify_package_tree(root: Path) -> dict[str, str]:
    expected = set(EXPECTED_PACKAGE_IDS)
    actual = (
        {path.name for path in root.iterdir() if path.is_dir()}
        if root.exists()
        else set()
    )
    missing = sorted(expected - actual)
    unexpected = sorted(actual - expected)
    if missing or unexpected:
        raise ValueError(
            f"native package set mismatch; missing={missing}, unexpected={unexpected}"
        )
    digests: dict[str, str] = {}
    for package_id in EXPECTED_PACKAGE_IDS:
        package = root / package_id
        absent = [name for name in REQUIRED_FILES if not (package / name).is_file()]
        if absent:
            raise ValueError(f"{package_id} missing required files: {absent}")
        for json_name in (
            "question.json",
            "rights.json",
            "rubric.json",
            "solution.json",
            "metadata.json",
            "tests/public.json",
            "tests/hidden.json",
        ):
            try:
                json.loads((package / json_name).read_text(encoding="utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise ValueError(
                    f"{package_id}/{json_name} is not valid UTF-8 JSON"
                ) from exc
        digests[package_id] = _tree_digest(package)
    return digests


def install_packages(
    archive_directory: Path = DEFAULT_DIRECTORY,
    output: Path = DEFAULT_OUTPUT,
    *,
    force: bool = False,
) -> dict[str, object]:
    archive = assemble_archive(archive_directory)
    output.parent.mkdir(parents=True, exist_ok=True)
    installed: list[str] = []
    unchanged: list[str] = []
    with tempfile.TemporaryDirectory(
        prefix="rigor-python-packages-", dir=output.parent
    ) as temporary:
        staged = Path(temporary) / "staged"
        extract_archive(archive, staged)
        staged_digests = verify_package_tree(staged)
        output.mkdir(parents=True, exist_ok=True)
        for package_id in EXPECTED_PACKAGE_IDS:
            source = staged / package_id
            target = output / package_id
            if target.exists():
                if not target.is_dir():
                    raise ValueError(f"installation target is not a directory: {target}")
                if not force and _tree_digest(target) == staged_digests[package_id]:
                    unchanged.append(package_id)
                    continue
                if not force:
                    raise ValueError(
                        f"{package_id} already exists with different content; use --force"
                    )
                shutil.rmtree(target)
            os.replace(source, target)
            installed.append(package_id)
    installed_digests = verify_package_tree(output)
    return {
        "status": "installed",
        "archive_sha256": EXPECTED_ARCHIVE_SHA256,
        "packages": len(installed_digests),
        "installed": installed,
        "unchanged": unchanged,
        "digests": installed_digests,
    }


def check_packages(
    archive_directory: Path = DEFAULT_DIRECTORY,
    output: Path = DEFAULT_OUTPUT,
) -> dict[str, object]:
    archive = assemble_archive(archive_directory)
    with tempfile.TemporaryDirectory(
        prefix="rigor-python-package-check-"
    ) as temporary:
        staged = Path(temporary) / "staged"
        extract_archive(archive, staged)
        expected_digests = verify_package_tree(staged)
    installed_digests = verify_package_tree(output)
    mismatched = [
        package_id
        for package_id in EXPECTED_PACKAGE_IDS
        if expected_digests[package_id] != installed_digests[package_id]
    ]
    if mismatched:
        raise ValueError(f"installed native packages differ from archive: {mismatched}")
    return {
        "status": "valid",
        "archive_sha256": EXPECTED_ARCHIVE_SHA256,
        "packages": len(installed_digests),
        "digests": installed_digests,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--archive-directory", type=Path, default=DEFAULT_DIRECTORY)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    result = (
        check_packages(args.archive_directory, args.output)
        if args.check
        else install_packages(args.archive_directory, args.output, force=args.force)
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
