from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parents[3]


def load_collector() -> ModuleType:
    path = ROOT / "scripts" / "collect_external_references.py"
    spec = importlib.util.spec_from_file_location("rigor_external_reference_collector", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


collector = load_collector()


def test_metadata_classifier_produces_patterns_and_competencies() -> None:
    patterns, competencies = collector.classify_metadata(
        ["hash-maps", "distributed-computing", "concurrency"],
        ["algorithms"],
    )
    assert "indexed-lookup" in patterns
    assert "distributed-coordination" in patterns
    assert "algorithms" in competencies
    assert "data-structures" in competencies
    assert "distributed-systems" in competencies
    assert "reliability" in competencies


def test_policy_blocks_prohibited_sources_and_approves_only_reviewed_connectors() -> None:
    policy = json.loads(
        (ROOT / "content" / "sources" / "source-policy.json").read_text(encoding="utf-8")
    )
    sources = {source["domain"]: source for source in policy["sources"]}
    assert sources["leetcode.com"]["coverage_level"] == "BLOCKED"
    assert sources["hackerrank.com"]["coverage_level"] == "BLOCKED"
    assert sources["reddit.com"]["connector_status"] == "paused"
    assert sources["exercism.org"]["connector_status"] == "approved"
    assert sources["github.com"]["coverage_level"] == "METADATA_ONLY"
    assert all(
        source["coverage_level"] == "METADATA_ONLY"
        for source in sources.values()
        if source["connector_status"] == "approved"
    )
