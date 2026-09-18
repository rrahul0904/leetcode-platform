from __future__ import annotations

from rigor_api.mock_interview_domain import (
    build_report,
    evaluate_response,
    template_for,
    templates,
)


def test_mock_interview_templates_cover_core_skillforge_focuses() -> None:
    slugs = {template.slug for template in templates()}
    assert {
        "data-engineering",
        "python",
        "sql",
        "system-design",
        "ai-architecture",
        "staff-leadership",
    } <= slugs


def test_evaluate_response_rewards_matching_concepts_and_depth() -> None:
    template = template_for("data-engineering")
    assert template is not None
    phase = template.phases[0]

    weak = evaluate_response(phase, "I would ask about scale.")
    strong = evaluate_response(
        phase,
        (
            "I would clarify event volume and throughput, latency SLA and freshness, "
            "producer and downstream consumers, schema contracts, and data quality. "
            "I would quantify peak scale and identify correctness requirements before "
            "choosing streaming or batch boundaries."
        ),
    )

    assert strong.score > weak.score
    assert strong.concept_coverage > weak.concept_coverage
    assert strong.word_count > weak.word_count


def test_build_report_preserves_phase_evidence_and_bounds_score() -> None:
    template = template_for("python")
    assert template is not None
    evidence = [
        evaluate_response(
            phase,
            (
                "I would clarify concurrency, bounded capacity, FIFO ordering, timeout "
                "behavior, synchronization, testing, observability, and backpressure."
            ),
        )
        for phase in template.phases
    ]

    report = build_report(evidence)

    assert 0 <= report.overall_score <= 1
    assert len(report.rubric_evidence) == len(template.phases)
    assert report.strengths
    assert report.next_steps
