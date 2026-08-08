#!/usr/bin/env python3
"""Verify pinned upstream Git revisions against reviewed source fingerprints."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path, PurePosixPath
from typing import Final

try:
    from build_uploaded_question_bank import TEXT_EXTENSIONS
except ModuleNotFoundError:  # Imported from tests or repository root.
    from scripts.build_uploaded_question_bank import TEXT_EXTENSIONS

CODE_EXTENSIONS: Final = TEXT_EXTENSIONS - {".md"}


class VerificationError(RuntimeError):
    """Raised when the pinned source cannot be inspected or does not match."""


def _git(args: list[str], *, cwd: Path | None = None) -> str:
    command = ["git", *args]
    try:
        result = subprocess.run(
            command,
            cwd=cwd,
            check=True,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError as error:
        raise VerificationError("git executable is unavailable") from error
    except subprocess.CalledProcessError as error:
        detail = (error.stderr or error.stdout or "").strip()
        raise VerificationError(f"{' '.join(command)} failed: {detail}") from error
    return result.stdout


def _clone_exact(repository: str, commit: str, destination: Path) -> None:
    _git(["init", "--quiet", str(destination)])
    _git(["remote", "add", "origin", repository], cwd=destination)
    _git(["fetch", "--quiet", "--depth=1", "origin", commit], cwd=destination)


def _blob_paths(repository_root: Path, commit: str) -> list[str]:
    output = _git(["ls-tree", "-r", "--full-tree", commit], cwd=repository_root)
    paths: list[str] = []
    for raw in output.splitlines():
        if "\t" not in raw:
            continue
        metadata, path = raw.split("\t", 1)
        fields = metadata.split()
        if len(fields) >= 2 and fields[1] == "blob":
            paths.append(path)
    return paths


def _top_level_directories(repository_root: Path, commit: str) -> int:
    output = _git(["ls-tree", "-d", "--full-tree", commit], cwd=repository_root)
    return sum(1 for raw in output.splitlines() if "\t" in raw)


def summarize(repository_root: Path, commit: str) -> dict[str, object]:
    paths = _blob_paths(repository_root, commit)
    suffixes = Counter(PurePosixPath(path).suffix.casefold() for path in paths)
    code_files = sum(suffixes[extension] for extension in CODE_EXTENSIONS)
    code_language_extensions = sum(
        1 for extension in CODE_EXTENSIONS if suffixes[extension] > 0
    )
    return {
        "total_files": len(paths),
        "code_files": code_files,
        "code_language_extensions": code_language_extensions,
        "markdown_files": suffixes[".md"],
        "png_files": suffixes[".png"],
        "cpp_files": suffixes[".cpp"] + suffixes[".c++"],
        "javascript_files": suffixes[".js"],
        "python_files": suffixes[".py"],
        "top_level_directories": _top_level_directories(repository_root, commit),
        "extension_counts": dict(sorted(suffixes.items())),
    }


def parse_expectations(values: list[str]) -> dict[str, int]:
    expectations: dict[str, int] = {}
    for value in values:
        key, separator, raw_expected = value.partition("=")
        if not separator or not key or not raw_expected:
            raise VerificationError(f"invalid --expect value: {value!r}")
        try:
            expectations[key] = int(raw_expected)
        except ValueError as error:
            raise VerificationError(
                f"expected integer in --expect {value!r}"
            ) from error
    return expectations


def verify(summary: dict[str, object], expectations: dict[str, int]) -> None:
    failures: list[str] = []
    for key, expected in expectations.items():
        actual = summary.get(key)
        if actual != expected:
            failures.append(f"{key}: expected {expected}, got {actual!r}")
    if failures:
        raise VerificationError("; ".join(failures))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository", required=True)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--expect", action="append", default=[])
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    expectations = parse_expectations(args.expect)
    with tempfile.TemporaryDirectory(prefix="rigor-pinned-source-") as temporary:
        repository_root = Path(temporary) / "repository"
        _clone_exact(args.repository, args.commit, repository_root)
        summary = summarize(repository_root, args.commit)

    error_message: str | None = None
    try:
        verify(summary, expectations)
    except VerificationError as error:
        error_message = str(error)

    result: dict[str, object] = {
        "repository": args.repository,
        "commit": args.commit,
        "expected": expectations,
        "observed": summary,
        "verified": error_message is None,
    }
    if error_message is not None:
        result["error"] = error_message

    payload = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
    print(payload, end="")
    if error_message is not None:
        print(error_message, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
