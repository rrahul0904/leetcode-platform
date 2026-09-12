from __future__ import annotations

import pytest

from rigor_api.tutor_domain import (
    CandidateLevel,
    InterventionKind,
    SafeCodeContext,
    SafeWhiteboardContext,
    TutorContextSnapshot,
    TutorContextViolation,
    TutorMode,
    TutorSurface,
    WhiteboardNode,
    assert_tutor_context_is_public,
    decide_intervention,
    teaching_mix,
)


def test_private_evaluation_material_is_rejected_recursively() -> None:
    with pytest.raises(TutorContextViolation, match="hidden_tests"):
        assert_tutor_context_is_public(
            {
                "question": {"slug": "two-sum"},
                "execution": {
                    "public_tests": [{"passed": True}],
                    "hidden_tests": [{"expected": "secret"}],
                },
            }
        )


@pytest.mark.parametrize(
    ("level", "learn", "practice"),
    [
        (CandidateLevel.JUNIOR, 0.65, 0.35),
        (CandidateLevel.MID, 0.50, 0.50),
        (CandidateLevel.SENIOR, 0.30, 0.70),
        (CandidateLevel.STAFF, 0.15, 0.85),
        (CandidateLevel.MANAGER, 0.20, 0.80),
    ],
)
def test_teaching_mix_changes_with_seniority(
    level: CandidateLevel,
    learn: float,
    practice: float,
) -> None:
    mix = teaching_mix(level)
    assert mix.learn_share == learn
    assert mix.practice_share == practice


def test_mock_mode_stays_silent_while_candidate_is_working() -> None:
    intervention = decide_intervention(
        TutorContextSnapshot(
            mode=TutorMode.MOCK,
            surface=TutorSurface.CODE,
            candidate_level=CandidateLevel.SENIOR,
            idle_seconds=12,
            consecutive_failed_runs=0,
            code=SafeCodeContext(language="python", source="def solve(): pass"),
        )
    )

    assert intervention.kind is InterventionKind.SILENT
    assert intervention.should_speak is False
    assert intervention.may_reveal_solution is False


def test_mock_mode_nudges_after_sustained_stall_without_revealing_answer() -> None:
    intervention = decide_intervention(
        TutorContextSnapshot(
            mode=TutorMode.MOCK,
            surface=TutorSurface.CODE,
            candidate_level=CandidateLevel.MID,
            idle_seconds=120,
            code=SafeCodeContext(language="python", source=""),
        )
    )

    assert intervention.kind is InterventionKind.NUDGE
    assert intervention.should_speak is True
    assert intervention.may_reveal_solution is False


def test_repeated_public_failures_trigger_hint_in_practice() -> None:
    intervention = decide_intervention(
        TutorContextSnapshot(
            mode=TutorMode.PRACTICE,
            surface=TutorSurface.CODE,
            candidate_level=CandidateLevel.MID,
            consecutive_failed_runs=2,
            code=SafeCodeContext(
                language="python",
                source="def solve(nums): return []",
                public_tests_passed=1,
                public_tests_total=3,
                last_run_status="failed",
            ),
        )
    )

    assert intervention.kind is InterventionKind.HINT
    assert intervention.may_reveal_solution is False


def test_senior_candidate_gets_complexity_probe_after_public_tests_pass() -> None:
    intervention = decide_intervention(
        TutorContextSnapshot(
            mode=TutorMode.PRACTICE,
            surface=TutorSurface.CODE,
            candidate_level=CandidateLevel.SENIOR,
            code=SafeCodeContext(
                language="python",
                source="def solve(nums): return sorted(nums)",
                public_tests_passed=4,
                public_tests_total=4,
                last_run_status="passed",
            ),
        )
    )

    assert intervention.kind is InterventionKind.COMPLEXITY_CHALLENGE


def test_staff_whiteboard_gets_tradeoff_probe_once_design_has_shape() -> None:
    whiteboard = SafeWhiteboardContext(
        nodes=[
            WhiteboardNode(id="client", label="Client"),
            WhiteboardNode(id="api", label="API Gateway"),
            WhiteboardNode(id="queue", label="Queue"),
            WhiteboardNode(id="db", label="Primary DB"),
        ]
    )

    intervention = decide_intervention(
        TutorContextSnapshot(
            mode=TutorMode.PRACTICE,
            surface=TutorSurface.WHITEBOARD,
            candidate_level=CandidateLevel.STAFF,
            whiteboard=whiteboard,
        )
    )

    assert intervention.kind is InterventionKind.TRADEOFF_CHALLENGE
    assert intervention.should_speak is True
    assert intervention.may_reveal_solution is False


def test_explicit_help_request_overrides_observation() -> None:
    intervention = decide_intervention(
        TutorContextSnapshot(
            mode=TutorMode.PRACTICE,
            surface=TutorSurface.CHAT,
            candidate_level=CandidateLevel.JUNIOR,
            user_requested_help=True,
        )
    )

    assert intervention.kind is InterventionKind.HINT
    assert intervention.should_speak is True
