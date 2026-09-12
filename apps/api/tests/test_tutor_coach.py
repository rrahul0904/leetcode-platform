from dataclasses import replace

from rigor_api.tutor_coach import TutorCoachContext, deterministic_coach_reply
from rigor_api.tutor_domain import (
    CandidateLevel,
    InterventionKind,
    TutorIntervention,
    TutorMode,
)


def _context(message: str, *, source: str = "") -> TutorCoachContext:
    return TutorCoachContext(
        message=message,
        title="Two Sum Variant",
        problem_statement="Return the requested indices.",
        source=source,
        language="python3.13",
        elapsed_seconds=120,
        mode=TutorMode.PRACTICE,
        candidate_level=CandidateLevel.SENIOR,
        intervention=TutorIntervention(
            kind=InterventionKind.HINT,
            reason="candidate explicitly requested help",
            should_speak=True,
        ),
    )


def test_empty_draft_hint_is_socratic_not_a_solution() -> None:
    reply = deterministic_coach_reply(_context("give me a hint"))

    assert "invariant" in reply.text.lower()
    assert "answer key" not in reply.text.lower()
    assert "return [" not in reply.text.lower()


def test_complexity_reply_uses_observable_draft_signals() -> None:
    reply = deterministic_coach_reply(
        _context(
            "what is my complexity?",
            source=(
                "def solve(nums):\n"
                "    seen = {}\n"
                "    for value in nums:\n"
                "        seen[value] = True\n"
            ),
        )
    )

    assert "keyed lookup" in reply.text
    assert "time and space" in reply.text.lower()


def test_sql_coach_adapts_to_query_reasoning() -> None:
    context = replace(
        _context("help with edge cases", source="SELECT * FROM orders"),
        language="postgresql18",
    )

    reply = deterministic_coach_reply(context)

    assert "NULL" in reply.text
    assert "join" in reply.text.lower()
