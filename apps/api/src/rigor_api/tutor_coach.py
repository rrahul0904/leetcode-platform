"""Provider-neutral Socratic coaching for the candidate tutor.

The deterministic coach is the always-available baseline. It is intentionally
solution-averse: it reasons from candidate-owned draft code plus the public problem
statement and returns the next useful question or nudge instead of an answer key.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .tutor_domain import CandidateLevel, InterventionKind, TutorIntervention, TutorMode
from .tutor_mastery import TutorMasterySnapshot, mastery_focus


@dataclass(frozen=True)
class TutorCoachContext:
    message: str
    title: str
    problem_statement: str
    source: str
    language: str
    elapsed_seconds: int
    mode: TutorMode
    candidate_level: CandidateLevel
    intervention: TutorIntervention
    mastery: TutorMasterySnapshot = field(default_factory=TutorMasterySnapshot)


@dataclass(frozen=True)
class TutorCoachReply:
    text: str
    provider: str = "skillforge"
    model: str = "socratic-v1"


def _source_signals(source: str) -> list[str]:
    lowered = source.lower()
    signals: list[str] = []
    if not source.strip() or source.strip() in {"pass", "todo"}:
        return ["the draft is still at the starting point"]
    if "for " in lowered or "while " in lowered:
        signals.append("the draft iterates over data")
    if "for " in lowered and lowered.count("for ") >= 2:
        signals.append("there may be more than one traversal to account for")
    if any(token in lowered for token in ("dict", "defaultdict", "counter", "{")):
        signals.append("a keyed lookup structure appears in the draft")
    if any(token in lowered for token in ("set(", " set[", " set(")):
        signals.append("a set-like membership structure appears in the draft")
    if "sort(" in lowered or "sorted(" in lowered:
        signals.append("sorting appears in the draft")
    if "def " in lowered and "return" in lowered:
        signals.append("the draft has an executable function shape")
    return signals[:3] or ["there is enough draft code to reason about the next step"]


def _mastery_guidance(context: TutorCoachContext) -> str:
    """Turn evaluated learner evidence into a coaching emphasis, never a score write."""

    focus = mastery_focus(context.mastery)
    if focus is None or focus.mastery >= 0.75:
        return ""
    return (
        f" Your evaluated evidence for **{focus.name}** is still developing, so make that "
        "part of your reasoning explicit rather than skipping over it."
    )


def _sql_reply(context: TutorCoachContext, intent: str) -> str:
    title = context.title or "this query"
    if intent == "complexity":
        return (
            f"For **{title}**, reason about cost through row cardinality rather than Big-O alone. "
            "Which relation is largest, what does each join do to row count, and which filter can "
            "be applied earliest? Then check whether grouping, sorting, or a window step dominates."
            + _mastery_guidance(context)
        )
    if intent == "edge":
        return (
            "Try the query against four cases before changing it: no matching rows, duplicate join "
            "keys, NULL values on the optional side of a join, and ties in any "
            "ordering/window rule. Which one would change your current result shape?"
            + _mastery_guidance(context)
        )
    return (
        f"For **{title}**, describe the result grain in one sentence first: one row per *what*? "
        "Then walk each JOIN, filter, aggregation, or window clause and verify it preserves that "
        "grain. Make the smallest change that fixes the first place the grain stops matching."
        + _mastery_guidance(context)
    )


def _intent(message: str) -> str:
    lowered = message.casefold()
    if any(word in lowered for word in ("complexity", "big o", "runtime", "space")):
        return "complexity"
    if any(word in lowered for word in ("edge", "corner", "boundary", "case")):
        return "edge"
    if any(word in lowered for word in ("error", "fail", "wrong", "bug", "debug")):
        return "debug"
    if any(word in lowered for word in ("hint", "stuck", "help", "nudge")):
        return "hint"
    if any(word in lowered for word in ("approach", "idea", "strategy", "review")):
        return "approach"
    return "general"


def deterministic_coach_reply(context: TutorCoachContext) -> TutorCoachReply:
    """Return a useful, non-solution-revealing response without external dependencies."""

    intent = _intent(context.message)
    language = context.language.casefold()
    if "postgres" in language or language == "sql":
        return TutorCoachReply(text=_sql_reply(context, intent))

    signals = _source_signals(context.source)
    observation = "; ".join(signals)
    title = context.title or "this problem"
    mastery_guidance = _mastery_guidance(context)

    if context.mode is TutorMode.MOCK and context.intervention.kind is InterventionKind.NUDGE:
        return TutorCoachReply(
            text=(
                "Interviewer nudge: state the invariant you are trying to preserve, then name the "
                "single operation that must become cheaper or more reliable. I will stay quiet "
                "after that so you can drive the solution."
            )
        )

    if intent == "complexity":
        parts = [
            f"From the current draft, {observation}.",
            "Count the dominant operation for each input element, then multiply by the number of "
            "times that operation is performed.",
        ]
        if any("sorting" in signal for signal in signals):
            parts.append(
                "Because sorting appears in the draft, separate its cost from the later traversal."
            )
        if any("keyed lookup" in signal or "set-like" in signal for signal in signals):
            parts.append(
                "Also state the expected lookup cost and the extra memory used by that structure."
            )
        parts.append("What time and space bounds do you get from that accounting?")
        if mastery_guidance:
            parts.append(mastery_guidance.strip())
        return TutorCoachReply(text=" ".join(parts))

    if intent == "edge":
        return TutorCoachReply(
            text=(
                f"For **{title}**, test your reasoning against: the smallest valid input, repeated "
                "values, an answer at the first/last position, and a case where no early shortcut "
                "is available. Pick the case most likely to violate your current invariant and "
                "trace the draft line by line on it."
                f"{mastery_guidance}"
            )
        )

    if intent == "debug":
        return TutorCoachReply(
            text=(
                f"I can see that {observation}. Do not patch the symptom yet. Choose the smallest "
                "public example that fails, write down the state you expect immediately before the "
                "wrong value appears, and compare it with the state your code actually creates. "
                "Which variable first diverges?"
                f"{mastery_guidance}"
            )
        )

    if intent in {"hint", "approach"}:
        if not context.source.strip() or context.source.strip() in {"pass", "todo"}:
            text = (
                f"Start **{title}** by writing one sentence for the invariant and one sentence for "
                "the expensive operation in the brute-force approach. Then ask: what information "
                "could I remember so I do not repeat that work? Tell me those two sentences and I "
                "will give you the next nudge."
            )
        else:
            text = (
                f"Your current draft suggests that {observation}. "
                "Before adding more code, name the invariant each iteration/function call must "
                "preserve and identify the one line that establishes or updates it. If you cannot "
                "point to that line, that is the next thing to fix."
            )
        return TutorCoachReply(text=text + mastery_guidance)

    senior_probe = ""
    if context.candidate_level in {
        CandidateLevel.SENIOR,
        CandidateLevel.STAFF,
        CandidateLevel.MANAGER,
    }:
        senior_probe = (
            " After that, tell me the trade-off you made between simplicity, asymptotic cost, and "
            "memory."
        )
    return TutorCoachReply(
        text=(
            f"I am following **{title}** with your current draft. Right now, {observation}. "
            "What invariant are you relying on, and what is the next state transition your code "
            f"must make correctly?{senior_probe}{mastery_guidance}"
        )
    )
