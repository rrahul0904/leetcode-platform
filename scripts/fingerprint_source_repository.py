#!/usr/bin/env python3
"""Fingerprint historical Git trees for source-provenance recovery.

The corpus builder intentionally recognizes a narrow set of text/code extensions.
This tool starts from those same extensions, then adds common repository metadata
files that are useful for provenance matching but are not corpus content.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import tempfile
from collections.abc import Sequence
from dataclasses import asdict, dataclass, replace
from pathlib import Path, PurePosixPath

try:
    from build_uploaded_question_bank import TEXT_EXTENSIONS
except ModuleNotFoundError:  # Imported as scripts.fingerprint_source_repository in tests.
    from scripts.build_uploaded_question_bank import TEXT_EXTENSIONS

BUILDER_CODE_EXTENSIONS = TEXT_EXTENSIONS - {".md"}
PROVENANCE_TEXT_EXTENSIONS = TEXT_EXTENSIONS
PROVENANCE_BASENAMES = {
    "authors",
    "changelog",
    "code_of_conduct",
    "contributing",
    "copying",
    "license",
    "notice",
    "readme",
}
LANGUAGE_EXTENSIONS = {
    "c": {".c"},
    "cpp": {".cpp", ".c++"},
    "c++": {".cpp", ".c++"},
    "dart": {".dart"},
    "go": {".go"},
    "java": {".java"},
    "javascript": {".js"},
    "js": {".js"},
    "kotlin": {".kt"},
    "kt": {".kt"},
    "python": {".py"},
    "py": {".py"},
    "sql": {".sql"},
}
LICENSE_BASENAME_PREFIXES = ("license", "copying", "notice")


@dataclass(frozen=True)
class TreeEntry:
    path: str
    object_sha: str
    size: int


@dataclass(frozen=True)
class TreeFingerprint:
    commit: str
    tree_sha: str
    raw_entries: int
    useful_files: int
    code_files: int
    language_files: int
    language: str
    license_files: tuple[str, ...]
    license: str | None
    tree_bytes: int
    git_archive_bytes: int | None = None
    git_archive_sha256: str | None = None
    score: int = 0


@dataclass(frozen=True)
class Targets:
    raw_entries: int | None
    useful_files: int | None
    code_files: int | None
    language_files: int | None


class FingerprintError(RuntimeError):
    """Raised for genuine repository or Git execution failures."""


def _git(args: Sequence[str], *, cwd: Path | None = None) -> str:
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
        raise FingerprintError("git executable is unavailable") from error
    except subprocess.CalledProcessError as error:
        detail = (error.stderr or error.stdout or "").strip()
        raise FingerprintError(f"{' '.join(command)} failed: {detail}") from error
    return result.stdout


def _repository_name(repository: str) -> str:
    value = repository.rstrip("/").removesuffix(".git")
    return value.rsplit("/", 1)[-1]


def _useful_path(path: str) -> bool:
    item = PurePosixPath(path)
    suffix = item.suffix.casefold()
    name = item.name.casefold()
    stem = item.stem.casefold()
    if suffix in PROVENANCE_TEXT_EXTENSIONS:
        return True
    if name in PROVENANCE_BASENAMES or stem in PROVENANCE_BASENAMES:
        return True
    return name.startswith(LICENSE_BASENAME_PREFIXES)


def _license_path(path: str) -> bool:
    name = PurePosixPath(path).name.casefold()
    return name.startswith(LICENSE_BASENAME_PREFIXES)


def _infer_license(text: str) -> str | None:
    normalized = " ".join(text.casefold().split())
    if "permission is hereby granted, free of charge" in normalized:
        return "MIT"
    if "gnu general public license" in normalized:
        if "version 3" in normalized:
            return "GPL-3.0"
        if "version 2" in normalized:
            return "GPL-2.0"
        return "GPL"
    if "apache license" in normalized and "version 2.0" in normalized:
        return "Apache-2.0"
    if "bsd 3-clause" in normalized:
        return "BSD-3-Clause"
    if "mozilla public license" in normalized:
        return "MPL"
    return None


def _tree_entries(repository_root: Path, tree_sha: str) -> list[TreeEntry]:
    output = _git(["ls-tree", "-r", "-l", "--full-tree", tree_sha], cwd=repository_root)
    rows: list[TreeEntry] = []
    for raw in output.splitlines():
        if "\t" not in raw:
            continue
        metadata, path = raw.split("\t", 1)
        fields = metadata.split()
        if len(fields) < 4 or fields[1] != "blob":
            continue
        size_text = fields[3]
        size = int(size_text) if size_text.isdigit() else 0
        rows.append(TreeEntry(path=path, object_sha=fields[2], size=size))
    return rows


def _raw_entry_count(entries: Sequence[TreeEntry]) -> int:
    directories: set[str] = set()
    for entry in entries:
        parent = PurePosixPath(entry.path).parent
        while str(parent) not in {"", "."}:
            directories.add(parent.as_posix())
            parent = parent.parent
    return 1 + len(directories) + len(entries)


def summarize_tree(
    entries: Sequence[TreeEntry],
    *,
    commit: str,
    tree_sha: str,
    language: str,
    license: str | None = None,
) -> TreeFingerprint:
    extensions = LANGUAGE_EXTENSIONS.get(language.casefold())
    if extensions is None:
        raise FingerprintError(f"unsupported target language: {language}")
    useful = sum(_useful_path(entry.path) for entry in entries)
    code = sum(
        PurePosixPath(entry.path).suffix.casefold() in BUILDER_CODE_EXTENSIONS
        for entry in entries
    )
    language_count = sum(
        PurePosixPath(entry.path).suffix.casefold() in extensions for entry in entries
    )
    license_files = tuple(sorted(entry.path for entry in entries if _license_path(entry.path)))
    return TreeFingerprint(
        commit=commit,
        tree_sha=tree_sha,
        raw_entries=_raw_entry_count(entries),
        useful_files=useful,
        code_files=code,
        language_files=language_count,
        language=language.casefold(),
        license_files=license_files,
        license=license,
        tree_bytes=sum(entry.size for entry in entries),
    )


def _score(fingerprint: TreeFingerprint, targets: Targets) -> int:
    pairs = (
        (fingerprint.raw_entries, targets.raw_entries),
        (fingerprint.useful_files, targets.useful_files),
        (fingerprint.code_files, targets.code_files),
        (fingerprint.language_files, targets.language_files),
    )
    return sum(abs(actual - expected) for actual, expected in pairs if expected is not None)


def _matches(fingerprint: TreeFingerprint, targets: Targets) -> bool:
    checks = (
        targets.raw_entries is None or fingerprint.raw_entries == targets.raw_entries,
        targets.useful_files is None or fingerprint.useful_files == targets.useful_files,
        targets.code_files is None or fingerprint.code_files == targets.code_files,
        targets.language_files is None
        or fingerprint.language_files == targets.language_files,
    )
    return all(checks)


def rank_fingerprints(
    fingerprints: Sequence[TreeFingerprint],
    targets: Targets,
) -> list[TreeFingerprint]:
    ranked = [replace(item, score=_score(item, targets)) for item in fingerprints]
    return sorted(ranked, key=lambda item: (item.score, item.tree_bytes, item.commit))


def _license_for_tree(
    repository_root: Path,
    commit: str,
    entries: Sequence[TreeEntry],
    cache: dict[str, str | None],
) -> str | None:
    for entry in entries:
        if not _license_path(entry.path):
            continue
        if entry.object_sha not in cache:
            try:
                content = _git(["show", f"{commit}:{entry.path}"], cwd=repository_root)
            except FingerprintError:
                cache[entry.object_sha] = None
            else:
                cache[entry.object_sha] = _infer_license(content)
        detected = cache[entry.object_sha]
        if detected:
            return detected
    return None


def _archive_fingerprint(
    repository_root: Path,
    fingerprint: TreeFingerprint,
    *,
    prefix: str,
    archive_dir: Path | None,
) -> TreeFingerprint:
    destination_dir = archive_dir
    temporary: tempfile.TemporaryDirectory[str] | None = None
    if destination_dir is None:
        temporary = tempfile.TemporaryDirectory(prefix="rigor-source-archive-")
        destination_dir = Path(temporary.name)
    destination_dir.mkdir(parents=True, exist_ok=True)
    destination = destination_dir / f"{fingerprint.commit}.zip"
    try:
        _git(
            [
                "archive",
                "--format=zip",
                f"--prefix={prefix.rstrip('/')}/",
                f"--output={destination.resolve()}",
                fingerprint.commit,
            ],
            cwd=repository_root,
        )
        payload = destination.read_bytes()
        return replace(
            fingerprint,
            git_archive_bytes=len(payload),
            git_archive_sha256=hashlib.sha256(payload).hexdigest(),
        )
    finally:
        if temporary is not None:
            temporary.cleanup()


def scan_repository(
    repository: str,
    *,
    before_date: str,
    language: str,
    targets: Targets,
    limit: int,
    archive_top: int,
    archive_prefix: str | None,
    archive_dir: Path | None,
    work: Path,
) -> dict[str, object]:
    repository_root = work / "repository"
    if repository_root.exists():
        raise FingerprintError(f"work path already exists: {repository_root}")
    work.mkdir(parents=True, exist_ok=True)
    _git(
        [
            "clone",
            "--quiet",
            "--filter=blob:none",
            "--no-checkout",
            repository,
            str(repository_root),
        ]
    )
    log = _git(
        [
            "log",
            "--all",
            f"--before={before_date}",
            "--format=%H%x09%T",
            "--date-order",
        ],
        cwd=repository_root,
    )
    tree_to_commit: dict[str, str] = {}
    for line in log.splitlines():
        if "\t" not in line:
            continue
        commit, tree_sha = line.split("\t", 1)
        tree_to_commit.setdefault(tree_sha, commit)

    license_cache: dict[str, str | None] = {}
    fingerprints: list[TreeFingerprint] = []
    for tree_sha, commit in tree_to_commit.items():
        entries = _tree_entries(repository_root, tree_sha)
        license_name = _license_for_tree(repository_root, commit, entries, license_cache)
        fingerprints.append(
            summarize_tree(
                entries,
                commit=commit,
                tree_sha=tree_sha,
                language=language,
                license=license_name,
            )
        )

    ranked = rank_fingerprints(fingerprints, targets)
    prefix = archive_prefix or f"{_repository_name(repository)}-source"
    archived: dict[str, TreeFingerprint] = {}
    for item in ranked[: max(0, archive_top)]:
        archived[item.tree_sha] = _archive_fingerprint(
            repository_root,
            item,
            prefix=prefix,
            archive_dir=archive_dir,
        )
    final_ranked = [archived.get(item.tree_sha, item) for item in ranked]
    exact = [item for item in final_ranked if _matches(item, targets)]
    return {
        "repository": repository,
        "before_date": before_date,
        "language": language,
        "unique_trees_scanned": len(tree_to_commit),
        "targets": {
            "raw_entries": targets.raw_entries,
            "useful_files": targets.useful_files,
            "code_files": targets.code_files,
            "language_files": targets.language_files,
        },
        "exact_matches": [asdict(item) for item in exact],
        "ranked_matches": [asdict(item) for item in final_ranked[: max(1, limit)]],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository", required=True)
    parser.add_argument("--target-entries", type=int)
    parser.add_argument("--target-useful-files", type=int)
    parser.add_argument("--target-code-files", type=int)
    parser.add_argument("--target-language", required=True)
    parser.add_argument("--target-language-count", type=int)
    parser.add_argument("--before-date", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--limit", type=int, default=25)
    parser.add_argument("--archive-top", type=int, default=0)
    parser.add_argument("--archive-prefix")
    parser.add_argument("--archive-dir", type=Path)
    parser.add_argument("--work", type=Path)
    args = parser.parse_args()

    targets = Targets(
        raw_entries=args.target_entries,
        useful_files=args.target_useful_files,
        code_files=args.target_code_files,
        language_files=args.target_language_count,
    )
    work_context: tempfile.TemporaryDirectory[str] | None = None
    work = args.work
    if work is None:
        work_context = tempfile.TemporaryDirectory(prefix="rigor-source-fingerprint-")
        work = Path(work_context.name)

    try:
        result = scan_repository(
            args.repository,
            before_date=args.before_date,
            language=args.target_language,
            targets=targets,
            limit=max(1, args.limit),
            archive_top=max(0, args.archive_top),
            archive_prefix=args.archive_prefix,
            archive_dir=args.archive_dir,
            work=work,
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(result, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(json.dumps(result, sort_keys=True))
        return 0
    finally:
        if work_context is not None:
            work_context.cleanup()


if __name__ == "__main__":
    raise SystemExit(main())
