#!/usr/bin/env python3
"""Load the embedded, checksum-pinned Python source candidate batch."""

from __future__ import annotations

import hashlib
import json
import lzma
from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import Any, cast

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DIRECTORY = ROOT / "content" / "imported" / "source-backed"
PART_GLOB = "python-batch.xz.part[0-9][0-9]"
EXPECTED_PART_COUNT = 7
EXPECTED_COMPRESSED_SHA256 = (
    "dd28ba85814016e2c6444a4007c8d2b906f3412a9c619cf1c9906735d2de314e"
)
EXPECTED_JSONL_SHA256 = (
    "5b603cf110e993a464afd5c426f3b9ab10742ea0b8d32ec92f6feab7c64a0790"
)
EXPECTED_CANDIDATE_COUNT = 20
JsonObject = dict[str, Any]


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def assemble_batch(
    directory: Path = DEFAULT_DIRECTORY,
    *,
    expected_compressed_sha256: str = EXPECTED_COMPRESSED_SHA256,
    expected_part_count: int = EXPECTED_PART_COUNT,
) -> bytes:
    """Assemble the ordered xz parts and verify their aggregate checksum."""
    parts = sorted(directory.glob(PART_GLOB))
    if len(parts) != expected_part_count:
        raise ValueError(
            f"expected {expected_part_count} Python batch parts, found {len(parts)}"
        )
    compressed = b"".join(path.read_bytes() for path in parts)
    actual = _sha256(compressed)
    if actual != expected_compressed_sha256:
        raise ValueError(
            "Python batch compressed checksum mismatch: "
            f"expected {expected_compressed_sha256}, found {actual}"
        )
    return compressed


def parse_jsonl(data: bytes) -> list[JsonObject]:
    """Decode validated JSONL objects and enforce the focused-batch contract."""
    rows: list[JsonObject] = []
    ids: set[str] = set()
    slugs: set[str] = set()
    for line_number, raw in enumerate(data.splitlines(), 1):
        if not raw.strip():
            continue
        value: object = json.loads(raw)
        if not isinstance(value, dict):
            raise ValueError(f"Python batch line {line_number} must be a JSON object")
        row = cast(JsonObject, value)
        identifier = str(row.get("id") or "").strip()
        slug = str(row.get("slug") or "").strip()
        language = str(row.get("reference_solution_language") or "").strip()
        statement = str(row.get("problem_markdown") or "").strip()
        solution = str(row.get("reference_solution_code") or "").strip()
        if not identifier or not slug:
            raise ValueError(f"Python batch line {line_number} is missing id or slug")
        if identifier in ids:
            raise ValueError(f"duplicate Python batch id: {identifier}")
        if slug in slugs:
            raise ValueError(f"duplicate Python batch slug: {slug}")
        if language not in {"py", "python"}:
            raise ValueError(
                f"Python batch line {line_number} has unsupported language {language!r}"
            )
        if not statement or not solution:
            raise ValueError(
                f"Python batch line {line_number} must include statement and solution"
            )
        ids.add(identifier)
        slugs.add(slug)
        rows.append(row)
    return rows


def load_python_candidates(
    directory: Path = DEFAULT_DIRECTORY,
    *,
    expected_compressed_sha256: str = EXPECTED_COMPRESSED_SHA256,
    expected_jsonl_sha256: str = EXPECTED_JSONL_SHA256,
    expected_part_count: int = EXPECTED_PART_COUNT,
    expected_candidate_count: int = EXPECTED_CANDIDATE_COUNT,
) -> list[JsonObject]:
    """Return the checksum-pinned, validated Python candidate records."""
    compressed = assemble_batch(
        directory,
        expected_compressed_sha256=expected_compressed_sha256,
        expected_part_count=expected_part_count,
    )
    try:
        jsonl = lzma.decompress(compressed)
    except lzma.LZMAError as exc:
        raise ValueError("Python batch is not a valid xz payload") from exc
    actual_jsonl_sha256 = _sha256(jsonl)
    if actual_jsonl_sha256 != expected_jsonl_sha256:
        raise ValueError(
            "Python batch JSONL checksum mismatch: "
            f"expected {expected_jsonl_sha256}, found {actual_jsonl_sha256}"
        )
    rows = parse_jsonl(jsonl)
    if len(rows) != expected_candidate_count:
        raise ValueError(
            f"expected {expected_candidate_count} Python candidates, found {len(rows)}"
        )
    return rows


def iter_python_candidates(
    directory: Path = DEFAULT_DIRECTORY,
) -> Iterator[JsonObject]:
    """Yield validated records without exposing the compressed representation."""
    yield from load_python_candidates(directory)


def summarize_candidates(rows: Iterable[JsonObject]) -> dict[str, object]:
    """Return a deterministic, candidate-safe summary for CI and operators."""
    materialized = list(rows)
    return {
        "count": len(materialized),
        "ids": [str(row["id"]) for row in materialized],
        "slugs": [str(row["slug"]) for row in materialized],
    }


def main() -> int:
    print(
        json.dumps(
            summarize_candidates(load_python_candidates()),
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
