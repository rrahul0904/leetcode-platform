from rigor_api.tutor_coach import TutorCoachContext
from rigor_api.tutor_domain import (
    CandidateLevel,
    InterventionKind,
    TutorIntervention,
    TutorMode,
)
from rigor_api.tutor_provider import build_tutor_provider_service


def _context() -> TutorCoachContext:
    return TutorCoachContext(
        message="give me a hint",
        title="Two Sum Variant",
        problem_statement="Return the requested indices.",
        source="",
        language="python3.13",
        elapsed_seconds=30,
        mode=TutorMode.PRACTICE,
        candidate_level=CandidateLevel.SENIOR,
        intervention=TutorIntervention(
            kind=InterventionKind.HINT,
            reason="candidate requested help",
            should_speak=True,
        ),
    )


def test_deterministic_adapter_is_the_default_provider() -> None:
    reply = build_tutor_provider_service("DETERMINISTIC").respond(_context())

    assert reply.provider == "skillforge"
    assert reply.model == "socratic-v1"
    assert "invariant" in reply.text.lower()


def test_unavailable_configured_provider_falls_back_without_network_dispatch() -> None:
    reply = build_tutor_provider_service("NOT_YET_BOUND").respond(_context())

    assert reply.provider == "skillforge-fallback"
    assert reply.model == "socratic-v1"
    assert "invariant" in reply.text.lower()
