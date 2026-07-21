#!/usr/bin/env python3
"""Populate the external reference catalog from reviewed metadata-only connectors.

The collector deliberately excludes problem statements, answers, solutions, tests,
premium fields, and user profile data. Source policy is applied before any sync.
"""

from __future__ import annotations

import argparse
import html
import json
import os
import ssl
import sys
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from rigor_api.question_intelligence import QuestionIntelligenceRepository
from rigor_api.schemas import (
    AuthenticatedPrincipal,
    ConnectorStatus,
    CoverageLevel,
    ExternalReferenceInput,
    Role,
    SourceReviewInput,
    SourceRightsStatus,
    SourceSyncInput,
)
from rigor_api.source_registry import SourceRegistryRepository
from sqlalchemy import create_engine

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATABASE_URL = "postgresql+psycopg://rigor:rigor_local_only@localhost:5434/rigor"
POLICY_PATH = ROOT / "content" / "sources" / "source-policy.json"
CODEWARS_SEEDS_PATH = ROOT / "content" / "sources" / "codewars-seeds.json"
USER_AGENT = "rigor-reference-catalog/0.1 (+https://github.com/rrahul0904/leetcode-platform)"

EXERCISM_TRACKS: dict[str, tuple[str, ...]] = {
    "python": ("python-engineering", "algorithms", "data-structures"),
    "javascript": ("algorithms", "data-structures", "backend-engineering"),
    "typescript": ("algorithms", "data-structures", "backend-engineering"),
    "java": ("algorithms", "data-structures", "backend-engineering"),
    "go": ("algorithms", "backend-engineering", "distributed-systems"),
    "rust": ("algorithms", "backend-engineering", "operating-systems"),
    "cpp": ("algorithms", "data-structures", "operating-systems"),
    "csharp": ("algorithms", "data-structures", "backend-engineering"),
}

STACK_OVERFLOW_TAGS: dict[str, tuple[str, ...]] = {
    "algorithm": ("algorithms",),
    "data-structures": ("data-structures", "algorithms"),
    "python": ("python-engineering",),
    "sql": ("sql", "databases"),
    "database": ("databases", "data-modeling"),
    "concurrency": ("backend-engineering", "operating-systems", "reliability"),
    "machine-learning": ("machine-learning",),
    "security": ("security",),
    "networking": ("networking",),
    "kubernetes": ("cloud-infrastructure", "reliability"),
}

SOFTWARE_ENGINEERING_TAGS: dict[str, tuple[str, ...]] = {
    "architecture": ("system-design", "backend-engineering"),
    "distributed-computing": ("distributed-systems", "reliability"),
    "design-patterns": ("system-design", "backend-engineering"),
}

TOPIC_COMPETENCIES: dict[str, tuple[str, ...]] = {
    "array": ("data-structures", "algorithms"),
    "arrays": ("data-structures", "algorithms"),
    "list": ("data-structures",),
    "linked-list": ("data-structures", "algorithms"),
    "map": ("data-structures",),
    "hash": ("data-structures", "algorithms"),
    "tree": ("data-structures", "algorithms"),
    "graph": ("data-structures", "algorithms"),
    "search": ("algorithms",),
    "sort": ("algorithms",),
    "recursion": ("algorithms",),
    "dynamic-programming": ("algorithms",),
    "database": ("databases", "data-modeling"),
    "sql": ("sql", "databases"),
    "concurrency": ("backend-engineering", "operating-systems", "reliability"),
    "distributed": ("distributed-systems", "reliability"),
    "network": ("networking",),
    "security": ("security",),
    "machine-learning": ("machine-learning",),
    "observability": ("observability", "reliability"),
    "reliability": ("reliability",),
    "cloud": ("cloud-infrastructure",),
    "kubernetes": ("cloud-infrastructure", "reliability"),
}

PATTERN_RULES: dict[str, str] = {
    "array": "sequence-processing",
    "list": "sequence-processing",
    "string": "string-processing",
    "map": "indexed-lookup",
    "hash": "indexed-lookup",
    "tree": "tree-traversal",
    "graph": "graph-traversal",
    "search": "search",
    "sort": "ordering",
    "recursion": "recursive-decomposition",
    "dynamic-programming": "dynamic-programming",
    "concurrency": "concurrency-control",
    "distributed": "distributed-coordination",
    "sql": "relational-querying",
    "database": "data-persistence",
    "security": "threat-mitigation",
    "kubernetes": "container-orchestration",
}


class JsonClient:
    def __init__(self, ca_file: str | None) -> None:
        self.context = ssl.create_default_context(cafile=ca_file) if ca_file else None
        if self.context is not None and hasattr(ssl, "VERIFY_X509_STRICT"):
            # Python 3.13 enables strict X.509 checks that reject some enterprise
            # interception roots. Keep chain and hostname verification enabled,
            # but use the compatibility policy accepted by curl and system tools.
            self.context.verify_flags &= ~ssl.VERIFY_X509_STRICT

    def get(self, url: str) -> dict[str, Any]:
        request = Request(
            url,
            headers={"Accept": "application/json", "User-Agent": USER_AGENT},
        )
        with urlopen(request, timeout=30, context=self.context) as response:
            value = json.loads(response.read().decode("utf-8"))
        if not isinstance(value, dict):
            raise ValueError(f"Expected a JSON object from {url}")
        return cast(dict[str, Any], value)


def unique_strings(values: Iterable[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))


def normalized_tokens(values: Iterable[str]) -> set[str]:
    tokens: set[str] = set()
    for value in values:
        normalized = value.casefold().replace("_", "-").replace(" ", "-")
        tokens.add(normalized)
        tokens.update(part for part in normalized.split("-") if part)
    return tokens


def classify_metadata(
    topics: Iterable[str], fallback_competencies: Iterable[str]
) -> tuple[list[str], list[str]]:
    tokens = normalized_tokens(topics)
    competencies = list(fallback_competencies)
    patterns: list[str] = []
    joined = " ".join(sorted(tokens))
    for keyword, mapped in TOPIC_COMPETENCIES.items():
        if keyword in tokens or keyword in joined:
            competencies.extend(mapped)
    for keyword, pattern in PATTERN_RULES.items():
        if keyword in tokens or keyword in joined:
            patterns.append(pattern)
    return unique_strings(patterns), unique_strings(competencies)


def difficulty_from_exercism(value: object) -> str:
    if not isinstance(value, int):
        return "unrated"
    if value <= 3:
        return "foundational"
    if value <= 6:
        return "intermediate"
    return "advanced"


def collect_exercism(client: JsonClient) -> list[ExternalReferenceInput]:
    references: list[ExternalReferenceInput] = []
    for track, fallback in EXERCISM_TRACKS.items():
        config = client.get(f"https://raw.githubusercontent.com/exercism/{track}/main/config.json")
        exercises = cast(dict[str, Any], config.get("exercises", {}))
        for collection_name in ("concept", "practice"):
            collection_value = exercises.get(collection_name, [])
            if not isinstance(collection_value, list):
                continue
            collection = cast(list[object], collection_value)
            for raw_exercise in collection:
                if not isinstance(raw_exercise, dict):
                    continue
                exercise = cast(dict[str, Any], raw_exercise)
                if exercise.get("status") == "deprecated":
                    continue
                slug = str(exercise.get("slug", "")).strip()
                name = str(exercise.get("name", "")).strip()
                if not slug or not name:
                    continue
                topic_value = cast(
                    object, exercise.get("practices") or exercise.get("concepts") or []
                )
                topic_values = (
                    cast(list[object], topic_value) if isinstance(topic_value, list) else []
                )
                topics = [str(value) for value in topic_values if isinstance(value, str)]
                prerequisites = [
                    str(value)
                    for value in cast(list[object], exercise.get("prerequisites") or [])
                    if isinstance(value, str)
                ]
                patterns, competencies = classify_metadata(topics + prerequisites, fallback)
                references.append(
                    ExternalReferenceInput(
                        source_external_id=f"{track}:{slug}",
                        canonical_url=f"https://exercism.org/tracks/{track}/exercises/{slug}",
                        title=name,
                        difficulty=difficulty_from_exercism(exercise.get("difficulty")),
                        topic_metadata=unique_strings([track, *topics, *prerequisites]),
                        patterns=patterns,
                        competency_slugs=competencies,
                        source_metadata={
                            "platform": "Exercism",
                            "track": track,
                            "exercise_kind": collection_name,
                            "status": str(exercise.get("status", "active")),
                            "license": "MIT",
                            "metadata_origin": f"https://github.com/exercism/{track}/blob/main/config.json",
                            "difficulty_basis": "official-track-config-or-unrated",
                        },
                    )
                )
    return references


def collect_github_open_exercises(client: JsonClient) -> list[ExternalReferenceInput]:
    repository = "exercism/problem-specifications"
    repository_data = client.get(f"https://api.github.com/repos/{repository}")
    license_data = cast(dict[str, Any], repository_data.get("license") or {})
    spdx_id = str(license_data.get("spdx_id") or "")
    if spdx_id != "MIT":
        raise ValueError(f"Refusing GitHub collection: expected MIT, received {spdx_id!r}")
    default_branch = str(repository_data.get("default_branch") or "main")
    tree = client.get(
        f"https://api.github.com/repos/{repository}/git/trees/{default_branch}?recursive=1"
    )
    paths: set[str] = set()
    for raw_item in cast(list[object], tree.get("tree") or []):
        if not isinstance(raw_item, dict):
            continue
        item = cast(dict[str, object], raw_item)
        path = str(item.get("path", ""))
        if path.startswith("exercises/") and path.endswith("/canonical-data.json"):
            paths.add(path)
    references: list[ExternalReferenceInput] = []
    for path in sorted(paths):
        parts = path.split("/")
        if len(parts) < 3:
            continue
        slug = parts[1]
        topics = slug.split("-")
        patterns, competencies = classify_metadata(topics, ("algorithms",))
        references.append(
            ExternalReferenceInput(
                source_external_id=f"{repository}:{slug}",
                canonical_url=(
                    f"https://github.com/{repository}/tree/{default_branch}/exercises/{slug}"
                ),
                title=slug.replace("-", " ").title(),
                difficulty="unrated",
                topic_metadata=topics,
                patterns=patterns,
                competency_slugs=competencies,
                source_metadata={
                    "platform": "GitHub",
                    "repository": repository,
                    "path": f"exercises/{slug}",
                    "license": spdx_id,
                    "difficulty_basis": "repository-does-not-publish-difficulty",
                },
            )
        )
    return references


def collect_stack_exchange_site(
    client: JsonClient,
    *,
    site: str,
    tags: dict[str, tuple[str, ...]],
) -> list[ExternalReferenceInput]:
    by_id: dict[str, ExternalReferenceInput] = {}
    for tag, fallback in tags.items():
        query = urlencode(
            {
                "site": site,
                "pagesize": 100,
                "page": 1,
                "order": "desc",
                "sort": "votes",
                "tagged": tag,
                "filter": "default",
            }
        )
        payload = client.get(f"https://api.stackexchange.com/2.3/questions?{query}")
        if payload.get("backoff"):
            raise RuntimeError("Stack Exchange requested backoff; stop and retry later")
        for item in cast(list[dict[str, Any]], payload.get("items") or []):
            question_id = str(item.get("question_id", ""))
            link = str(item.get("link", ""))
            if not question_id or not link.startswith("https://"):
                continue
            item_tags = [str(value) for value in cast(list[object], item.get("tags") or [])]
            patterns, competencies = classify_metadata(item_tags, fallback)
            existing = by_id.get(question_id)
            if existing:
                existing.topic_metadata = unique_strings([*existing.topic_metadata, *item_tags])
                existing.patterns = unique_strings([*existing.patterns, *patterns])
                existing.competency_slugs = unique_strings(
                    [*existing.competency_slugs, *competencies]
                )
                continue
            by_id[question_id] = ExternalReferenceInput(
                source_external_id=question_id,
                canonical_url=link,
                title=html.unescape(str(item.get("title", ""))),
                difficulty="unrated",
                topic_metadata=item_tags,
                patterns=patterns,
                competency_slugs=competencies,
                source_metadata={
                    "platform": "Stack Exchange",
                    "site": site,
                    "content_license": str(item.get("content_license", "CC BY-SA")),
                    "score": int(item.get("score", 0)),
                    "view_count": int(item.get("view_count", 0)),
                    "answer_count": int(item.get("answer_count", 0)),
                    "is_answered": bool(item.get("is_answered", False)),
                    "creation_date": int(item.get("creation_date", 0)),
                    "last_activity_date": int(item.get("last_activity_date", 0)),
                    "attribution_required": True,
                    "difficulty_basis": "source-does-not-publish-difficulty",
                },
                technology_freshness="fast_moving",
            )
    return list(by_id.values())


def collect_codewars(client: JsonClient) -> list[ExternalReferenceInput]:
    seed_payload = cast(dict[str, Any], json.loads(CODEWARS_SEEDS_PATH.read_text()))
    references: list[ExternalReferenceInput] = []
    for identifier in cast(list[str], seed_payload["identifiers"]):
        item = client.get(f"https://www.codewars.com/api/v1/code-challenges/{identifier}")
        item_tags = [str(value) for value in cast(list[object], item.get("tags") or [])]
        patterns, competencies = classify_metadata(item_tags, ("algorithms",))
        rank = cast(dict[str, Any], item.get("rank") or {})
        canonical_slug = str(item.get("slug") or identifier)
        references.append(
            ExternalReferenceInput(
                source_external_id=str(item.get("id") or canonical_slug),
                canonical_url=f"https://www.codewars.com/kata/{canonical_slug}",
                title=str(item.get("name") or canonical_slug.replace("-", " ").title()),
                difficulty=str(rank.get("name") or "unrated"),
                topic_metadata=item_tags,
                patterns=patterns,
                competency_slugs=competencies,
                source_metadata={
                    "platform": "Codewars",
                    "category": str(item.get("category") or ""),
                    "languages": cast(list[object], item.get("languages") or []),
                    "rank_id": rank.get("id"),
                    "total_attempts": int(item.get("totalAttempts", 0)),
                    "total_completed": int(item.get("totalCompleted", 0)),
                    "vote_score": int(item.get("voteScore", 0)),
                    "metadata_origin": "official-codewars-v1-api",
                    "description_stored": False,
                },
            )
        )
    return references


def load_policy() -> dict[str, Any]:
    value = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("source policy must be a JSON object")
    return cast(dict[str, Any], value)


def collector_principal() -> AuthenticatedPrincipal:
    now = datetime.now(UTC)
    return AuthenticatedPrincipal(
        subject_id="service:external-reference-collector",
        email="external-reference-collector@rigor.local",
        display_name="External Reference Collector",
        roles=[Role.platform_administrator],
        permissions=["sources:manage", "sources:sync", "content:read"],
        authentication_provider="service-account",
        token_issued_at=now,
        correlation_id=f"external-reference-sync-{now:%Y%m%dT%H%M%SZ}",
    )


def apply_source_policy(
    repository: SourceRegistryRepository,
    principal: AuthenticatedPrincipal,
    policy: dict[str, Any],
) -> dict[str, Any]:
    sources = {source.canonical_domain: source for source in repository.list(principal)}
    reviewed: dict[str, Any] = {}
    for raw_policy in cast(list[dict[str, Any]], policy["sources"]):
        source_policy = raw_policy
        domain = str(source_policy["domain"])
        source = sources.get(domain)
        if source is None:
            raise ValueError(f"Source policy references unregistered domain {domain}")
        configuration: dict[str, object] = {
            "policy_version": str(policy["policy_version"]),
            "evidence_urls": cast(list[object], source_policy.get("evidence_urls") or []),
            "metadata_only": str(source_policy["coverage_level"]) == "METADATA_ONLY",
        }
        reviewed[domain] = repository.review(
            principal,
            source.source_id,
            SourceReviewInput(
                rights_status=SourceRightsStatus(str(source_policy["rights_status"])),
                coverage_level=CoverageLevel(str(source_policy["coverage_level"])),
                collection_mode=str(source_policy["collection_mode"]),
                connector_status=ConnectorStatus(str(source_policy["connector_status"])),
                connector_type=str(source_policy["connector_type"]),
                connector_configuration=configuration,
                review_notes=str(source_policy["review_notes"]),
            ),
        )
    return reviewed


def synchronize(
    repository: SourceRegistryRepository,
    principal: AuthenticatedPrincipal,
    source: Any,
    references: list[ExternalReferenceInput],
) -> dict[str, int]:
    totals = {"discovered": 0, "created": 0, "updated": 0, "unavailable": 0}
    for offset in range(0, len(references), 1000):
        batch = references[offset : offset + 1000]
        result = repository.sync(
            principal,
            source.source_id,
            SourceSyncInput(
                sync_mode="initial_backfill" if offset == 0 else "incremental",
                cursor_before={"offset": offset} if offset else None,
                cursor_after={"offset": offset + len(batch)},
                references=batch,
                complete_snapshot=len(references) <= 1000,
            ),
        )
        totals["discovered"] += result.discovered_count
        totals["created"] += result.created_count
        totals["updated"] += result.updated_count
        totals["unavailable"] += result.unavailable_count
    return totals


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--database-url", default=os.getenv("RIGOR_DATABASE_URL", DEFAULT_DATABASE_URL)
    )
    parser.add_argument("--ca-file", default=os.getenv("SSL_CERT_FILE"))
    parser.add_argument(
        "--sources",
        nargs="*",
        choices=["codewars", "exercism", "github", "stackoverflow", "stackexchange"],
        default=["codewars", "exercism", "github", "stackoverflow", "stackexchange"],
    )
    args = parser.parse_args()
    engine = create_engine(args.database_url, pool_pre_ping=True)
    principal = collector_principal()
    repository = SourceRegistryRepository(engine)
    policy = load_policy()
    reviewed = apply_source_policy(repository, principal, policy)
    client = JsonClient(args.ca_file)
    collectors = {
        "codewars": ("codewars.com", lambda: collect_codewars(client)),
        "exercism": ("exercism.org", lambda: collect_exercism(client)),
        "github": ("github.com", lambda: collect_github_open_exercises(client)),
        "stackoverflow": (
            "stackoverflow.com",
            lambda: collect_stack_exchange_site(
                client, site="stackoverflow", tags=STACK_OVERFLOW_TAGS
            ),
        ),
        "stackexchange": (
            "stackexchange.com",
            lambda: collect_stack_exchange_site(
                client, site="softwareengineering", tags=SOFTWARE_ENGINEERING_TAGS
            ),
        ),
    }
    report: dict[str, object] = {
        "policy_version": str(policy["policy_version"]),
        "started_at": datetime.now(UTC).isoformat(),
        "sources": {},
    }
    source_report = cast(dict[str, object], report["sources"])
    for collector_name in args.sources:
        domain, collect = collectors[collector_name]
        print(f"collecting {collector_name} metadata", file=sys.stderr)
        references = collect()
        source_report[collector_name] = synchronize(
            repository, principal, reviewed[domain], references
        )
    gaps = QuestionIntelligenceRepository(engine).recompute_gaps(principal)
    report["completed_at"] = datetime.now(UTC).isoformat()
    report["coverage_gaps"] = gaps.model_dump(mode="json")
    print(json.dumps(report, indent=2, sort_keys=True))
    engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
