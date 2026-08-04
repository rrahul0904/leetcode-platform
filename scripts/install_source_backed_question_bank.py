#!/usr/bin/env python3
"""Validate and install a generated source-backed bank into the repository."""

from __future__ import annotations

import argparse
import base64
import json
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TARGET = (
    ROOT / "content" / "imported" / "source-backed" / "question-bank.zip.b64"
)
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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("archive", type=Path)
    parser.add_argument("--target", type=Path, default=DEFAULT_TARGET)
    args = parser.parse_args()

    with zipfile.ZipFile(args.archive) as bundle:
        names = set(bundle.namelist())
        missing = REQUIRED_FILES - names
        if missing:
            raise ValueError(f"question-bank archive is missing {sorted(missing)}")
        manifest = json.loads(bundle.read("manifest.json"))
    for key, expected in EXPECTED.items():
        actual = manifest.get(key)
        if actual != expected:
            raise ValueError(f"{key}: expected {expected}, found {actual}")

    args.target.parent.mkdir(parents=True, exist_ok=True)
    encoded = base64.b64encode(args.archive.read_bytes()).decode("ascii")
    args.target.write_text(encoded + "\n", encoding="ascii")
    print(
        f"installed {args.archive} at {args.target} "
        f"({len(encoded):,} base64 characters)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
