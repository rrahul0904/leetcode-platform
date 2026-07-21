#!/usr/bin/env python3
"""Generate the reviewed-plan manifest skeleton deterministically.

This script creates planning metadata only. It never creates published questions.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "content" / "question-bank-manifest.json"


@dataclass(frozen=True)
class Track:
    code: str
    slug: str
    name: str
    target: int
    topics: tuple[str, ...]
    skills: tuple[str, ...]
    companies: tuple[str, ...]


TRACKS = (
    Track(
        "PY",
        "python-engineering",
        "Python engineering",
        150,
        (
            "bounded cache",
            "dependency graph",
            "event stream",
            "interval index",
            "async worker pool",
            "retry scheduler",
            "resource manager",
            "typed API client",
            "memory profiler",
            "task deduplicator",
            "graph traversal",
            "streaming parser",
            "concurrent crawler",
            "plugin registry",
            "rate limiter",
            "batch pipeline",
            "transaction coordinator",
            "service health monitor",
            "immutable collection",
            "production debugger",
        ),
        ("python", "algorithms", "concurrency", "testing", "reliability"),
        ("google-style", "meta-style", "stripe-style", "openai-style"),
    ),
    Track(
        "SQL",
        "sql-analytics",
        "SQL and analytics engineering",
        150,
        (
            "retention cohort",
            "conversion funnel",
            "temporal ledger",
            "session boundary",
            "late event reconciliation",
            "experiment metric",
            "inventory snapshot",
            "identity deduplication",
            "rolling percentile",
            "hierarchy traversal",
            "subscription state",
            "fraud sequence",
            "revenue recognition",
            "SCD history",
            "data quality audit",
            "capacity trend",
            "ranking model",
            "JSON event normalization",
            "incremental aggregate",
            "lock contention diagnosis",
        ),
        ("sql", "postgresql", "analytics", "query-optimization", "data-quality"),
        ("databricks-style", "snowflake-style", "stripe-style", "netflix-style"),
    ),
    Track(
        "DM",
        "data-modeling",
        "Data modeling",
        100,
        (
            "multi-tenant billing",
            "consent history",
            "feature registry",
            "conversation memory",
            "event ledger",
            "content catalog",
            "identity graph",
            "recommendation feedback",
            "experiment assignment",
            "customer 360",
            "temporal inventory",
            "governance metadata",
            "vector document",
            "subscription entitlement",
            "financial ledger",
            "IoT telemetry",
            "health audit",
            "marketplace order",
            "workflow state",
            "training dataset",
        ),
        ("data-modeling", "relational-design", "temporal-data", "privacy", "governance"),
        ("snowflake-style", "databricks-style", "stripe-style", "scale-ai-style"),
    ),
    Track(
        "DA",
        "data-architecture",
        "Data architecture",
        120,
        (
            "lakehouse migration",
            "data contract platform",
            "lineage system",
            "privacy deletion pipeline",
            "real-time analytics platform",
            "metadata control plane",
            "master data service",
            "quality observability platform",
            "cross-region replication",
            "tenant-isolated warehouse",
            "event schema registry",
            "batch-to-stream migration",
            "regulated data mesh",
            "reconciliation platform",
            "feature data platform",
            "retention enforcement",
            "data product marketplace",
            "CDC platform",
            "analytical serving layer",
            "enterprise ingestion gateway",
        ),
        ("data-architecture", "governance", "lineage", "migration", "reliability"),
        ("databricks-style", "snowflake-style", "palantir-style", "scale-ai-style"),
    ),
    Track(
        "DS",
        "distributed-systems",
        "Distributed systems",
        150,
        (
            "replicated counter",
            "lease service",
            "distributed queue",
            "consistent cache",
            "membership service",
            "log replication",
            "idempotent workflow",
            "sharded metadata store",
            "global rate limiter",
            "distributed lock",
            "change-data stream",
            "failure detector",
            "multi-region write path",
            "backpressure controller",
            "exactly-once illusion",
            "quorum store",
            "task scheduler",
            "hot-key mitigator",
            "snapshot protocol",
            "reconciliation loop",
        ),
        ("distributed-systems", "consistency", "replication", "partitioning", "failure-recovery"),
        ("google-style", "meta-style", "cloudflare-style", "amazon-style"),
    ),
    Track(
        "SD",
        "system-design",
        "General system design",
        160,
        (
            "notification platform",
            "collaborative editor",
            "payment API",
            "media feed",
            "ride dispatch",
            "reservation system",
            "metrics pipeline",
            "search autocomplete",
            "file synchronization",
            "webhook delivery",
            "feature flag service",
            "audit platform",
            "fraud decision API",
            "content moderation queue",
            "URL platform",
            "messaging service",
            "marketplace checkout",
            "geospatial search",
            "API gateway",
            "developer portal",
        ),
        ("system-design", "api-design", "capacity-planning", "reliability", "observability"),
        ("amazon-style", "meta-style", "stripe-style", "uber-style"),
    ),
    Track(
        "ML",
        "ml-system-design",
        "Machine-learning system design",
        100,
        (
            "ranking platform",
            "fraud model",
            "recommendation service",
            "feature store",
            "training orchestrator",
            "experiment platform",
            "drift monitor",
            "forecasting pipeline",
            "online feature service",
            "model registry",
            "label quality system",
            "batch scoring platform",
            "real-time personalization",
            "cold-start model",
            "human review loop",
            "privacy-aware training",
            "multimodal classifier",
            "causal measurement",
            "model rollback",
            "training-serving consistency",
        ),
        (
            "ml-system-design",
            "training",
            "feature-engineering",
            "experimentation",
            "model-monitoring",
        ),
        ("netflix-style", "meta-style", "google-deepmind-style", "scale-ai-style"),
    ),
    Track(
        "GA",
        "generative-ai-architecture",
        "Generative AI and LLM architecture",
        140,
        (
            "enterprise RAG",
            "coding assistant",
            "citation research agent",
            "prompt experiment platform",
            "multi-model gateway",
            "voice assistant",
            "conversation memory",
            "document understanding",
            "semantic cache",
            "hybrid retrieval",
            "reranking service",
            "tool-use platform",
            "long-context pipeline",
            "multimodal assistant",
            "support agent",
            "embedding service",
            "prompt registry",
            "tenant-aware agent",
            "fine-tuning pipeline",
            "LLM observability",
        ),
        ("generative-ai", "rag", "agents", "evaluation", "privacy"),
        ("openai-style", "anthropic-style", "google-deepmind-style", "microsoft-style"),
    ),
    Track(
        "INF",
        "ai-infrastructure",
        "AI infrastructure and model serving",
        90,
        (
            "GPU scheduler",
            "continuous batching",
            "model router",
            "inference autoscaler",
            "distributed training fabric",
            "checkpoint service",
            "quantized serving",
            "speculative decoding",
            "model artifact registry",
            "capacity broker",
            "accelerator telemetry",
            "batch inference",
            "streaming inference",
            "memory-aware placement",
            "multi-region serving",
            "canary model rollout",
            "training data loader",
            "fault-tolerant collective",
            "cost attribution",
            "model warm pool",
        ),
        ("ai-infrastructure", "gpu-systems", "model-serving", "scheduling", "performance"),
        ("nvidia-style", "openai-style", "anthropic-style", "google-deepmind-style"),
    ),
    Track(
        "SAFE",
        "ai-safety-agents-evaluation",
        "AI agents, evaluation, safety, and alignment",
        80,
        (
            "durable agent runtime",
            "evaluation harness",
            "red-team platform",
            "prompt injection defense",
            "tool permission system",
            "misuse monitoring",
            "human escalation",
            "hallucination audit",
            "safety policy engine",
            "evaluation dataset",
            "agent trace store",
            "data exfiltration defense",
            "alignment experiment platform",
            "contamination detector",
            "guardrail gateway",
            "sandboxed tool runner",
            "safety incident response",
            "tenant consent service",
            "agent rollback",
            "evidence grader",
        ),
        ("agents", "evaluation", "ai-safety", "security", "human-oversight"),
        ("anthropic-style", "openai-style", "scale-ai-style", "google-deepmind-style"),
    ),
    Track(
        "LEAD",
        "staff-principal-leadership",
        "Staff and principal engineering leadership",
        60,
        (
            "platform consolidation",
            "multi-year migration",
            "architecture governance",
            "technical strategy",
            "cost transformation",
            "reliability program",
            "security ownership",
            "developer platform adoption",
            "cross-team API standard",
            "build-versus-buy decision",
            "organization-wide deprecation",
            "capacity investment",
            "technical debt portfolio",
            "operating model",
            "data governance program",
            "AI platform rollout",
            "executive risk review",
            "acquisition integration",
            "incident learning program",
            "talent and succession",
        ),
        ("technical-leadership", "strategy", "influence", "governance", "migration"),
        ("amazon-style", "google-style", "microsoft-style", "openai-style"),
    ),
    Track(
        "BEH",
        "behavioral-execution",
        "Behavioral, execution, incident, and architecture-review scenarios",
        50,
        (
            "cross-team disagreement",
            "failed launch",
            "production incident",
            "underperforming project",
            "ambiguous ownership",
            "executive escalation",
            "mentoring challenge",
            "security disclosure",
            "ethical AI decision",
            "priority conflict",
            "migration resistance",
            "cost overrun",
            "quality regression",
            "hiring decision",
            "architecture exception",
            "customer-impact trade-off",
            "missed commitment",
            "organizational change",
            "postmortem conflict",
            "strategy reversal",
        ),
        ("behavioral", "execution", "incident-management", "communication", "leadership"),
        ("amazon-style", "meta-style", "google-style", "anthropic-style"),
    ),
)

CONTEXTS = (
    "a regulated enterprise",
    "a global consumer product",
    "a multi-tenant platform",
    "a latency-critical service",
    "a cost-constrained growth stage",
    "a multi-region migration",
    "an incident-prone legacy estate",
    "a privacy-sensitive workflow",
)

LENSES = (
    "with correctness under retries",
    "during a zero-downtime migration",
    "under partial regional failure",
    "with tenfold demand growth",
    "with strict cost and ownership limits",
    "after a critical production incident",
)

DIFFICULTY_CYCLE = (
    "foundational",
    "intermediate",
    "advanced",
    "staff",
    "advanced",
    "intermediate",
    "advanced",
    "principal",
    "staff",
    "advanced",
    "foundational",
    "intermediate",
    "intermediate",
    "advanced",
    "advanced",
    "advanced",
    "staff",
    "staff",
    "staff",
    "principal",
)

ROLE_BY_DIFFICULTY = {
    "foundational": "senior",
    "intermediate": "senior",
    "advanced": "senior",
    "staff": "staff",
    "principal": "principal",
}

DURATION_BY_DIFFICULTY = {
    "foundational": 30,
    "intermediate": 40,
    "advanced": 55,
    "staff": 75,
    "principal": 90,
}


def entry(track: Track, local_index: int, global_index: int) -> dict[str, object]:
    topic = track.topics[local_index % len(track.topics)]
    context = CONTEXTS[(local_index // len(track.topics)) % len(CONTEXTS)]
    lens = LENSES[(local_index // (len(track.topics) * len(CONTEXTS))) % len(LENSES)]
    difficulty = DIFFICULTY_CYCLE[global_index % len(DIFFICULTY_CYCLE)]
    identifier = f"{track.code}-{local_index + 1:04d}"
    title = f"{track.name}: {topic.title()} for {context} {lens}"
    company_offset = local_index % len(track.companies)
    company_tags = [
        track.companies[company_offset],
        track.companies[(company_offset + 1) % len(track.companies)],
    ]
    return {
        "id": identifier,
        "working_title": title,
        "slug": f"{identifier.lower()}-{topic.replace(' ', '-')}",
        "primary_track": track.slug,
        "skills": [*track.skills[:3], topic.replace(" ", "-")],
        "difficulty": difficulty,
        "role_level": ROLE_BY_DIFFICULTY[difficulty],
        "company_style_tags": company_tags,
        "learning_objective": (
            f"Evaluate and justify a production approach to {topic} in {context}, "
            f"including trade-offs, failure behavior, and operational ownership."
        ),
        "estimated_duration_minutes": DURATION_BY_DIFFICULTY[difficulty],
        "content_status": "planned",
        "originality_status": "not_yet_authored",
        "difficulty_calibration": "provisional",
    }


def main() -> None:
    questions: list[dict[str, object]] = []
    global_index = 0
    for track in TRACKS:
        for local_index in range(track.target):
            questions.append(entry(track, local_index, global_index))
            global_index += 1

    manifest = {
        "manifest_version": "1.0.0",
        "generated_at": "2026-07-20T00:00:00Z",
        "foundation_milestone_count": 1350,
        "disclaimer": (
            "Planning metadata only. No entry is complete, validated, published, "
            "or claimed to have appeared in an employer interview."
        ),
        "track_targets": {track.slug: track.target for track in TRACKS},
        "questions": questions,
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {len(questions)} planned entries to {OUTPUT}")


if __name__ == "__main__":
    main()
