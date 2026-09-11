"""Tutor domain contracts and deterministic intervention policy.

This module is intentionally provider-neutral. It defines the safe context that an
AI tutor may observe and the first deterministic policy layer deciding *when* the
tutor may interrupt. Provider/realtime transport is added above this boundary.

Security invariant: hidden tests, expected hidden outputs, reference solutions and
interviewer-only material must never enter a TutorContextSnapshot.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class TutorModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class TutorMode(StrEnum):
    LESSON = "lesson"
    ROADMAP = "roadmap"
    PRACTICE = "practice"
    MOCK = "mock"


class TutorSurface(StrEnum):
    CHAT = "chat"
    CODE = "code"
    WHITEBOARD = "whiteboard"


class CandidateLevel(StrEnum):
    JUNIOR = "junior"
    MID = "mid"
    SENIOR = "senior"
    STAFF = "staff"
    MANAGER = "manager"


class InterventionKind(StrEnum):
    OBSERVE = "observe"
    SILENT = "silent"
    CONCEPT_CHECK = "concept_check"
    NUDGE = "nudge"
    HINT = "hint"
    COMPLEXITY_CHALLENGE = "complexity_challenge"
    TRADEOFF_CHALLENGE = "tradeoff_challenge"


class TeachingMix(TutorModel):
    learn_share: float = Field(ge=0, le=1)
    practice_share: float = Field(ge=0, le=1)


TEACHING_MIX: dict[CandidateLevel, TeachingMix] = {
    CandidateLevel.JUNIOR: TeachingMix(learn_share=0.65, practice_share=0.35),
    CandidateLevel.MID: TeachingMix(learn_share=0.50, practice_share=0.50),
    CandidateLevel.SENIOR: TeachingMix(learn_share=0.30, practice_share=0.70),
    CandidateLevel.STAFF: TeachingMix(learn_share=0.15, practice_share=0.85),
    # Managers are evaluated more on reasoning, delivery and trade-offs than coding
    # volume. Keep a practice-heavy split while the prompt layer changes the rubric.
    CandidateLevel.MANAGER: TeachingMix(learn_share=0.20, practice_share=0.80),
}


class SafeCodeContext(TutorModel):
    language: str = Field(min_length=1, max_length=40)
    source: str = Field(default="", max_length=100_000)
    public_tests_passed: int = Field(default=0, ge=0)
    public_tests_total: int = Field(default=0, ge=0)
    last_run_status: str | None = Field(default=None, max_length=80)
    public_error_summary: str | None = Field(default=None, max_length=4_000)


class WhiteboardNode(TutorModel):
    id: str = Field(min_length=1, max_length=120)
    label: str = Field(min_length=1, max_length=500)
    kind: str | None = Field(default=None, max_length=120)


class WhiteboardEdge(TutorModel):
    source: str = Field(min_length=1, max_length=120)
    target: str = Field(min_length=1, max_length=120)
    label: str | None = Field(default=None, max_length=300)


class SafeWhiteboardContext(TutorModel):
    nodes: list[WhiteboardNode] = Field(default_factory=list, max_length=250)
    edges: list[WhiteboardEdge] = Field(default_factory=list, max_length=500)
    requirements: list[str] = Field(default_factory=list, max_length=100)
    notes: list[str] = Field(default_factory=list, max_length=100)


class TutorContextSnapshot(TutorModel):
    mode: TutorMode
    surface: TutorSurface
    candidate_level: CandidateLevel
    question_slug: str | None = Field(default=None, max_length=200)
    public_problem_summary: str | None = Field(default=None, max_length=12_000)
    current_competencies: list[str] = Field(default_factory=list, max_length=100)
    code: SafeCodeContext | None = None
    whiteboard: SafeWhiteboardContext | None = None
    elapsed_seconds: int = Field(default=0, ge=0)
    idle_seconds: int = Field(default=0, ge=0)
    consecutive_failed_runs: int = Field(default=0, ge=0)
    user_requested_help: bool = False


class TutorIntervention(TutorModel):
    kind: InterventionKind
    reason: str
    may_reveal_solution: bool = False
    should_speak: bool = False


class TutorContextViolation(ValueError):
    """Raised when privileged evaluation material reaches tutor context assembly."""


_FORBIDDEN_CONTEXT_KEYS = frozenset(
    {
        "hidden_test",
        "hidden_tests",
        "hidden_fixture",
        "hidden_fixtures",
        "hidden_expected",
        "reference_solution",
        "canonical_solution",
        "solution_code",
        "interviewer_notes",
        "answer_key",
        "private_evaluation",
    }
)


def assert_tutor_context_is_public(value: Any, *, path: str = "context") -> None:
    """Fail closed if a raw context candidate contains privileged evaluation keys."""

    if isinstance(value, Mapping):
        for raw_key, child in value.items():
            key = str(raw_key).strip().lower()
            child_path = f"{path}.{raw_key}"
            if key in _FORBIDDEN_CONTEXT_KEYS:
                raise TutorContextViolation(
                    f"Privileged tutor context key is forbidden: {child_path}"
                )
            assert_tutor_context_is_public(child, path=child_path)
        return

    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for index, child in enumerate(value):
            assert_tutor_context_is_public(child, path=f"{path}[{index}]")


def teaching_mix(level: CandidateLevel) -> TeachingMix:
    return TEACHING_MIX[level]


def decide_intervention(snapshot: TutorContextSnapshot) -> TutorIntervention:
    """Choose a conservative tutor action from observable candidate state.

    This policy is deterministic on purpose. The model may decide *what to say* only
    after this layer decides whether it is allowed to say anything at all.
    """

    if snapshot.user_requested_help:
        return TutorIntervention(
            kind=InterventionKind.HINT,
            reason="candidate explicitly requested help",
            should_speak=True,
        )

    # Mock interviews should feel like an interviewer, not autocomplete. Stay quiet
    # while the candidate is making progress; intervene only on a sustained stall or
    # repeated observable failure.
    if snapshot.mode is TutorMode.MOCK:
        if snapshot.idle_seconds < 90 and snapshot.consecutive_failed_runs < 2:
            return TutorIntervention(
                kind=InterventionKind.SILENT,
                reason="mock mode preserves candidate thinking time",
            )
        return TutorIntervention(
            kind=InterventionKind.NUDGE,
            reason="candidate appears stalled in mock mode",
            should_speak=True,
        )

    if snapshot.surface is TutorSurface.CODE and snapshot.code is not None:
        if snapshot.consecutive_failed_runs >= 2:
            return TutorIntervention(
                kind=InterventionKind.HINT,
                reason="repeated public execution failures indicate a useful intervention point",
                should_speak=True,
            )
        if (
            snapshot.code.public_tests_total > 0
            and snapshot.code.public_tests_passed == snapshot.code.public_tests_total
            and snapshot.candidate_level
            in {CandidateLevel.SENIOR, CandidateLevel.STAFF, CandidateLevel.MANAGER}
        ):
            return TutorIntervention(
                kind=InterventionKind.COMPLEXITY_CHALLENGE,
                reason="solution passes public tests; probe complexity and edge-case reasoning",
                should_speak=True,
            )

    if snapshot.surface is TutorSurface.WHITEBOARD and snapshot.whiteboard is not None:
        if len(snapshot.whiteboard.nodes) >= 4 and teaching_mix(
            snapshot.candidate_level
        ).practice_share >= 0.70:
            return TutorIntervention(
                kind=InterventionKind.TRADEOFF_CHALLENGE,
                reason="senior candidate has enough architecture on the board for a trade-off probe",
                should_speak=True,
            )

    if snapshot.mode is TutorMode.LESSON:
        return TutorIntervention(
            kind=InterventionKind.CONCEPT_CHECK,
            reason="lesson mode periodically checks understanding instead of only explaining",
            should_speak=True,
        )

    return TutorIntervention(
        kind=InterventionKind.OBSERVE,
        reason="no intervention threshold reached",
    )
