#!/usr/bin/env python3
"""Validate and install the checksum-pinned source-backed bank."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import re
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIRECTORY = ROOT / "content" / "imported" / "source-backed"
DEFAULT_TARGET = SOURCE_DIRECTORY / "question-bank.zip.b64"
DEFAULT_CHECKSUM = SOURCE_DIRECTORY / "archive.sha256"
EXPECTED = {
    "unique_company_index_questions": 3424,
    "statement_backed_hosted_candidates": 121,
    "hosted_candidates_with_reference_solution": 120,
    "system_design_resources": 29,
}
REQUIRED_FILES = {
    "external_question_index.jsonl",
    "hosted_question_candidates.jsonl",
    "system_design_resources.jsonl",
    "manifest.json",
}
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


def read_expected_sha256(path: Path = DEFAULT_CHECKSUM) -> str:
    fields = path.read_text(encoding="ascii").strip().split()
    if not fields or not SHA256_PATTERN.fullmatch(fields[0].casefold()):
        raise ValueError(f"invalid SHA-256 checksum file: {path}")
    return fields[0].casefold()


def validate_archive(
    archive: Path,
    *,
    expected_sha256: str,
) -> tuple[bytes, dict[str, object]]:
    archive_bytes = archive.read_bytes()
    actual_sha256 = hashlib.sha256(archive_bytes).hexdigest()
    if actual_sha256 != expected_sha256:
        raise ValueError(
            "question-bank archive checksum mismatch: "
            f"expected {expected_sha256}, found {actual_sha256}"
        )

    with zipfile.ZipFile(archive) as bundle:
        names = set(bundle.namelist())
        missing = REQUIRED_FILES - names
        if missing:
            raise ValueError(f"question-bank archive is missing {sorted(missing)}")
        manifest_value: object = json.loads(bundle.read("manifest.json"))
    if not isinstance(manifest_value, dict):
        raise ValueError("manifest.json must contain a JSON object")
    manifest = dict(manifest_value)
    for key, expected in EXPECTED.items():
        actual = manifest.get(key)
        if actual != expected:
            raise ValueError(f"{key}: expected {expected}, found {actual}")
    return archive_bytes, manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("archive", type=Path)
    parser.add_argument("--target", type=Path, default=DEFAULT_TARGET)
    parser.add_argument("--checksum-file", type=Path, default=DEFAULT_CHECKSUM)
    args = parser.parse_args()

    expected_sha256 = read_expected_sha256(args.checksum_file)
    archive_bytes, _ = validate_archive(
        args.archive,
        expected_sha256=expected_sha256,
    )

    args.target.parent.mkdir(parents=True, exist_ok=True)
    encoded = base64.b64encode(archive_bytes).decode("ascii")
    args.target.write_text(encoded + "\n", encoding="ascii")
    print(
        f"installed checksum-pinned {args.archive} at {args.target} "
        f"(sha256={expected_sha256}, {len(encoded):,} base64 characters)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
