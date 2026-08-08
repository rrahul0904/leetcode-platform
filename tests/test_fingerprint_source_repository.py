from __future__ import annotations

from scripts.fingerprint_source_repository import (
    Targets,
    TreeEntry,
    rank_fingerprints,
    summarize_tree,
)


def _entry(path: str, *, size: int = 10) -> TreeEntry:
    return TreeEntry(path=path, object_sha=("a" * 40), size=size)


def test_fingerprint_counts_match_builder_text_semantics() -> None:
    entries = [
        _entry("solutions/one.cpp"),
        _entry("solutions/two.c++"),
        _entry("solutions/readme.md"),
        _entry("LICENSE"),
        _entry("config/settings.yml"),
        _entry("assets/diagram.png"),
    ]

    fingerprint = summarize_tree(
        entries,
        commit="1" * 40,
        tree_sha="2" * 40,
        language="cpp",
        license="MIT",
    )

    assert fingerprint.raw_entries == 10
    assert fingerprint.useful_files == 4
    assert fingerprint.code_files == 2
    assert fingerprint.language_files == 2
    assert fingerprint.license_files == ("LICENSE",)
    assert fingerprint.tree_bytes == 60


def test_rank_fingerprints_prefers_exact_count_match() -> None:
    exact = summarize_tree(
        [_entry("a.js"), _entry("README.md")],
        commit="1" * 40,
        tree_sha="2" * 40,
        language="javascript",
        license="MIT",
    )
    near = summarize_tree(
        [_entry("a.js"), _entry("b.js"), _entry("README.md")],
        commit="3" * 40,
        tree_sha="4" * 40,
        language="javascript",
        license="MIT",
    )
    targets = Targets(
        raw_entries=3,
        useful_files=2,
        code_files=1,
        language_files=1,
    )

    ranked = rank_fingerprints([near, exact], targets)

    assert ranked[0].tree_sha == exact.tree_sha
    assert ranked[0].score == 0
    assert ranked[1].score > 0
