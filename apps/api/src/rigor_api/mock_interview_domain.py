from __future__ import annotations

from dataclasses import dataclass
from statistics import mean


@dataclass(frozen=True)
class MockInterviewPhase:
    slug: str
    label: str
    prompt: str
    concept_groups: tuple[tuple[str, ...], ...]


@dataclass(frozen=True)
class MockInterviewTemplate:
    slug: str
    label: str
    description: str
    competencies: tuple[str, ...]
    phases: tuple[MockInterviewPhase, ...]


@dataclass(frozen=True)
class PhaseEvidence:
    phase: str
    label: str
    score: float
    concept_coverage: float
    depth_score: float
    matched_concepts: tuple[str, ...]
    missing_concepts: tuple[str, ...]
    word_count: int


@dataclass(frozen=True)
class InterviewReport:
    overall_score: float
    rubric_evidence: tuple[PhaseEvidence, ...]
    strengths: tuple[str, ...]
    growth_areas: tuple[str, ...]
    next_steps: tuple[str, ...]


def _phase(
    slug: str,
    label: str,
    prompt: str,
    *concept_groups: tuple[str, ...],
) -> MockInterviewPhase:
    return MockInterviewPhase(
        slug=slug,
        label=label,
        prompt=prompt,
        concept_groups=concept_groups,
    )


MOCK_INTERVIEW_TEMPLATES: dict[str, MockInterviewTemplate] = {
    "data-engineering": MockInterviewTemplate(
        slug="data-engineering",
        label="Data engineering",
        description=(
            "Design a production data platform while explaining requirements, "
            "data flow, reliability, scale, and trade-offs."
        ),
        competencies=(
            "data-architecture",
            "data-modeling",
            "distributed-systems",
            "reliability",
            "sql",
        ),
        phases=(
            _phase(
                "problem-framing",
                "Problem framing",
                (
                    "You need to design a platform that ingests operational events and "
                    "serves analytics within minutes. Clarify the requirements and the "
                    "questions you would ask before choosing an architecture."
                ),
                ("volume", "throughput", "events per", "scale"),
                ("latency", "sla", "freshness", "minutes"),
                ("source", "producer", "consumer", "downstream"),
                ("quality", "schema", "contract", "accuracy"),
            ),
            _phase(
                "pipeline-storage",
                "Pipeline & storage",
                (
                    "Propose the end-to-end ingestion, processing, storage, and serving "
                    "architecture. Explain how data moves and where contracts are enforced."
                ),
                ("batch", "stream", "streaming", "kafka", "queue"),
                ("warehouse", "lakehouse", "object storage", "table format"),
                ("partition", "cluster", "distribution", "sort key"),
                ("schema", "contract", "validation", "evolution"),
                ("idempot", "dedup", "exactly once", "replay"),
            ),
            _phase(
                "reliability-scale",
                "Reliability & scale",
                (
                    "Traffic doubles and one downstream warehouse becomes intermittent. "
                    "Explain how the platform stays correct, observable, and recoverable."
                ),
                ("retry", "backoff", "dead letter", "dlq"),
                ("checkpoint", "offset", "replay", "recovery"),
                ("backpressure", "buffer", "queue", "throttle"),
                ("monitor", "metric", "alert", "observability"),
                ("failure", "degrade", "fallback", "isolate"),
            ),
            _phase(
                "trade-offs",
                "Trade-offs",
                (
                    "Close the design by explaining the most important trade-offs, the "
                    "cost controls you would add, and what you would intentionally defer."
                ),
                ("cost", "budget", "compute", "storage"),
                ("latency", "freshness", "throughput"),
                ("consistency", "correctness", "availability"),
                ("complexity", "operational", "maintain"),
                ("defer", "phase", "later", "incremental"),
            ),
        ),
    ),
    "python": MockInterviewTemplate(
        slug="python",
        label="Python engineering",
        description=(
            "Work through a production Python problem from clarification through "
            "implementation strategy, testing, and operational follow-up."
        ),
        competencies=("python-engineering", "algorithms", "data-structures", "reliability"),
        phases=(
            _phase(
                "clarify",
                "Clarify",
                (
                    "You are asked to implement a bounded in-memory work queue used by "
                    "multiple producers. What do you clarify before writing code?"
                ),
                ("capacity", "bounded", "limit"),
                ("concurrency", "thread", "async", "producer"),
                ("ordering", "fifo", "priority"),
                ("failure", "timeout", "blocking", "backpressure"),
            ),
            _phase(
                "implement",
                "Implement",
                (
                    "Describe the data structures, public API, synchronization strategy, "
                    "and complexity of your implementation."
                ),
                ("deque", "queue", "heap", "data structure"),
                ("lock", "condition", "asyncio", "synchron"),
                ("enqueue", "dequeue", "put", "get"),
                ("o(1)", "complexity", "amortized"),
            ),
            _phase(
                "test",
                "Test",
                (
                    "Explain the tests that would give you confidence in correctness, "
                    "including concurrency and failure behavior."
                ),
                ("unit", "test case", "property", "invariant"),
                ("concurr", "race", "thread", "parallel"),
                ("boundary", "empty", "full", "capacity"),
                ("timeout", "failure", "cancel", "error"),
            ),
            _phase(
                "production-follow-up",
                "Production follow-up",
                (
                    "The queue works locally but latency spikes under load. Explain how "
                    "you would diagnose and harden it for production."
                ),
                ("profile", "latency", "benchmark", "measure"),
                ("metric", "trace", "log", "observability"),
                ("contention", "lock", "hotspot", "backpressure"),
                ("limit", "load", "capacity", "shed"),
            ),
        ),
    ),
    "sql": MockInterviewTemplate(
        slug="sql",
        label="SQL reasoning",
        description=(
            "Reason from schema and business grain to a correct query, edge-case "
            "validation, and an execution-plan optimization strategy."
        ),
        competencies=("sql", "databases", "data-modeling"),
        phases=(
            _phase(
                "inspect-schema",
                "Inspect schema",
                (
                    "A fact table contains orders and a dimension contains customer "
                    "history. Explain the grain, keys, and assumptions you verify first."
                ),
                ("grain", "one row", "level"),
                ("primary key", "foreign key", "key"),
                ("duplicate", "uniqu", "cardinality"),
                ("null", "missing", "history", "scd"),
            ),
            _phase(
                "write-query",
                "Write query",
                (
                    "You need monthly revenue and active customers by current segment. "
                    "Describe the SQL shape and how you avoid double counting."
                ),
                ("group by", "aggregate", "sum"),
                ("join", "dimension", "fact"),
                ("distinct", "dedup", "double count"),
                ("date_trunc", "month", "date"),
            ),
            _phase(
                "edge-cases",
                "Validate edge cases",
                (
                    "What data conditions could make the result wrong even if the query "
                    "runs successfully, and how would you test them?"
                ),
                ("null", "missing"),
                ("duplicate", "many-to-many", "cardinality"),
                ("timezone", "date boundary", "late"),
                ("zero", "negative", "refund", "cancel"),
            ),
            _phase(
                "optimize",
                "Optimize",
                (
                    "The query now scans billions of rows. Explain how you would inspect "
                    "the plan and reduce work without changing the business result."
                ),
                ("explain", "plan", "profile"),
                ("index", "partition", "cluster", "pruning"),
                ("predicate", "filter", "pushdown"),
                ("material", "pre-aggregate", "incremental", "cache"),
            ),
        ),
    ),
    "system-design": MockInterviewTemplate(
        slug="system-design",
        label="System design",
        description=(
            "Run a senior system-design interview from requirements and capacity "
            "through architecture, failure handling, and operational trade-offs."
        ),
        competencies=(
            "system-design",
            "distributed-systems",
            "backend-engineering",
            "reliability",
            "observability",
        ),
        phases=(
            _phase(
                "requirements",
                "Requirements",
                (
                    "Design a globally available notification service. Start by defining "
                    "functional requirements, non-functional requirements, and scope."
                ),
                ("functional", "send", "delivery", "notification"),
                ("latency", "availability", "sla"),
                ("scale", "throughput", "users", "requests"),
                ("scope", "assumption", "out of scope"),
            ),
            _phase(
                "capacity",
                "Capacity",
                (
                    "Estimate the traffic, storage, and burst capacity that materially "
                    "affect the design. State assumptions rather than chasing precision."
                ),
                ("qps", "rps", "throughput", "per second"),
                ("burst", "peak", "headroom"),
                ("storage", "retention", "bytes", "gb", "tb"),
                ("assumption", "estimate", "order of magnitude"),
            ),
            _phase(
                "architecture",
                "Architecture",
                (
                    "Walk through the main services, queues, stores, APIs, and data flow "
                    "from request acceptance to provider delivery."
                ),
                ("api", "gateway", "service"),
                ("queue", "broker", "kafka", "sqs"),
                ("database", "store", "cache"),
                ("worker", "consumer", "provider"),
                ("idempot", "dedup", "delivery"),
            ),
            _phase(
                "deep-dive",
                "Deep dive",
                (
                    "A provider is slow and retries cause duplicate notifications. Deep "
                    "dive into correctness, backpressure, retry, and isolation."
                ),
                ("retry", "backoff", "jitter"),
                ("idempot", "dedup", "exactly once"),
                ("backpressure", "queue", "throttle"),
                ("circuit breaker", "isolate", "bulkhead", "dead letter"),
            ),
            _phase(
                "operations",
                "Operations",
                (
                    "Close with observability, deployment, incident response, and the "
                    "trade-offs you would monitor after launch."
                ),
                ("metric", "trace", "log", "observability"),
                ("alert", "slo", "error budget"),
                ("deploy", "canary", "rollback"),
                ("incident", "runbook", "on-call"),
            ),
        ),
    ),
    "ai-architecture": MockInterviewTemplate(
        slug="ai-architecture",
        label="AI architecture",
        description=(
            "Design a production LLM feature with explicit evaluation, retrieval, "
            "safety, observability, latency, and cost boundaries."
        ),
        competencies=(
            "generative-ai",
            "ai-infrastructure",
            "ai-evaluation",
            "ai-safety",
            "system-design",
        ),
        phases=(
            _phase(
                "use-case",
                "Use case",
                (
                    "Design an assistant that answers questions over a company's private "
                    "technical documentation. Define the product and model boundaries."
                ),
                ("user", "use case", "task"),
                ("private", "permission", "tenant", "access"),
                ("latency", "availability", "sla"),
                ("ground", "citation", "source", "retrieval"),
            ),
            _phase(
                "evaluation",
                "Evaluation",
                (
                    "Explain how you would measure answer quality before launch and "
                    "continuously after launch."
                ),
                ("dataset", "golden", "benchmark", "test set"),
                ("precision", "recall", "faithful", "correct"),
                ("human", "review", "label"),
                ("online", "monitor", "drift", "feedback"),
            ),
            _phase(
                "architecture",
                "Architecture",
                (
                    "Walk through ingestion, chunking, retrieval, model calls, caching, "
                    "and how permissions flow through the system."
                ),
                ("chunk", "embed", "index"),
                ("retrieve", "rerank", "vector", "hybrid"),
                ("model", "llm", "gateway"),
                ("permission", "filter", "tenant", "acl"),
                ("cache", "context", "prompt"),
            ),
            _phase(
                "safety",
                "Safety",
                (
                    "Describe how the system handles prompt injection, sensitive data, "
                    "unsafe tool use, and unsupported claims."
                ),
                ("prompt injection", "untrusted", "instruction"),
                ("pii", "sensitive", "redact", "secret"),
                ("tool", "permission", "allowlist", "sandbox"),
                ("citation", "ground", "abstain", "hallucination"),
            ),
            _phase(
                "cost",
                "Cost & operations",
                (
                    "The product succeeds and model spend grows rapidly. Explain how you "
                    "would control cost while preserving quality and reliability."
                ),
                ("token", "cost", "budget"),
                ("cache", "batch", "smaller model", "route"),
                ("latency", "stream", "timeout"),
                ("metric", "trace", "observability", "usage"),
            ),
        ),
    ),
    "staff-leadership": MockInterviewTemplate(
        slug="staff-leadership",
        label="Staff leadership",
        description=(
            "Practice senior technical leadership through context, decision quality, "
            "influence, execution outcomes, and reflection."
        ),
        competencies=(
            "technical-leadership",
            "staff-engineering",
            "behavioral-competencies",
            "engineering-management",
        ),
        phases=(
            _phase(
                "context",
                "Context",
                (
                    "Describe a technically important program where teams disagreed on "
                    "architecture. Establish the context, constraints, and your role."
                ),
                ("context", "constraint", "goal", "problem"),
                ("team", "stakeholder", "organization"),
                ("role", "responsibility", "ownership"),
                ("risk", "deadline", "dependency"),
            ),
            _phase(
                "decisions",
                "Decisions",
                (
                    "Explain the hardest technical decision, the alternatives considered, "
                    "the evidence used, and why you chose the final direction."
                ),
                ("alternative", "option", "trade-off"),
                ("evidence", "data", "prototype", "benchmark"),
                ("decision", "choose", "recommend"),
                ("risk", "cost", "impact"),
            ),
            _phase(
                "influence",
                "Influence",
                (
                    "How did you create alignment without relying on authority, and how "
                    "did you handle strong disagreement?"
                ),
                ("listen", "understand", "disagree"),
                ("align", "stakeholder", "buy-in"),
                ("document", "rfc", "proposal"),
                ("facilitate", "mentor", "influence"),
            ),
            _phase(
                "outcomes",
                "Outcomes",
                (
                    "What measurable outcomes followed, what changed for customers or "
                    "engineering teams, and how did you know the decision worked?"
                ),
                ("metric", "measure", "result"),
                ("customer", "user", "business"),
                ("reliability", "latency", "cost", "delivery"),
                ("adoption", "team", "productivity"),
            ),
            _phase(
                "reflection",
                "Reflection",
                (
                    "What would you do differently now, and what principle from the "
                    "experience changed how you operate as a staff-level engineer?"
                ),
                ("different", "learn", "lesson"),
                ("feedback", "mistake", "improve"),
                ("principle", "framework", "approach"),
                ("next time", "future", "change"),
            ),
        ),
    ),
}


def template_for(slug: str) -> MockInterviewTemplate | None:
    return MOCK_INTERVIEW_TEMPLATES.get(slug)


def templates() -> tuple[MockInterviewTemplate, ...]:
    return tuple(MOCK_INTERVIEW_TEMPLATES.values())


def evaluate_response(phase: MockInterviewPhase, response: str) -> PhaseEvidence:
    normalized = " ".join(response.casefold().split())
    words = [word for word in normalized.split(" ") if word]
    matched: list[str] = []
    missing: list[str] = []
    for group in phase.concept_groups:
        label = group[0]
        if any(term.casefold() in normalized for term in group):
            matched.append(label)
        else:
            missing.append(label)
    concept_coverage = len(matched) / max(1, len(phase.concept_groups))
    depth_score = min(1.0, len(words) / 140)
    score = round((0.75 * concept_coverage) + (0.25 * depth_score), 4)
    return PhaseEvidence(
        phase=phase.slug,
        label=phase.label,
        score=score,
        concept_coverage=round(concept_coverage, 4),
        depth_score=round(depth_score, 4),
        matched_concepts=tuple(matched),
        missing_concepts=tuple(missing),
        word_count=len(words),
    )


def build_report(evidence: list[PhaseEvidence]) -> InterviewReport:
    if not evidence:
        return InterviewReport(
            overall_score=0.0,
            rubric_evidence=(),
            strengths=(),
            growth_areas=("No interview evidence was recorded.",),
            next_steps=("Complete a full mock interview.",),
        )

    overall = round(mean(item.score for item in evidence), 4)
    strengths = tuple(
        f"{item.label}: covered {len(item.matched_concepts)} rubric concepts with useful depth."
        for item in evidence
        if item.score >= 0.65
    )
    growth = tuple(
        f"{item.label}: strengthen {', '.join(item.missing_concepts[:3]) or 'response depth'}."
        for item in evidence
        if item.score < 0.65
    )
    weakest = sorted(evidence, key=lambda item: item.score)[:2]
    next_steps = tuple(
        f"Rehearse {item.label.casefold()} and explicitly address "
        f"{', '.join(item.missing_concepts[:3]) or 'the decision rationale'}."
        for item in weakest
    )
    return InterviewReport(
        overall_score=overall,
        rubric_evidence=tuple(evidence),
        strengths=strengths or ("Consistent completion across the interview phases.",),
        growth_areas=growth or ("Increase specificity with measurable evidence and trade-offs.",),
        next_steps=next_steps,
    )
