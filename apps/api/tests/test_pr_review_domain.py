from __future__ import annotations

import pytest

from rigor_api.pr_review_domain import (
    ReviewCommentInput,
    ReviewSeverity,
    ReviewVerdict,
    get_public_challenge,
    grade_review,
    review_location_is_valid,
)


def test_public_challenge_does_not_expose_hidden_findings() -> None:
    challenge = get_public_challenge("payments-retry-001")

    assert challenge is not None
    payload = challenge.model_dump(mode="json")
    assert payload["id"] == "payments-retry-001"
    assert "findings" not in payload
    assert "gold_findings" not in payload
    assert len(payload["files"]) == 3


def test_review_location_must_target_a_known_diff_line() -> None:
    assert review_location_is_valid(
        "payments-retry-001",
        "apps/api/src/payments/capture.ts",
        12,
    )
    assert not review_location_is_valid(
        "payments-retry-001",
        "apps/api/src/payments/capture.ts",
        999,
    )
    assert not review_location_is_valid(
        "missing-challenge",
        "apps/api/src/payments/capture.ts",
        12,
    )


def test_complete_review_receives_full_deterministic_score() -> None:
    comments = [
        ReviewCommentInput(
            file="apps/api/src/payments/capture.ts",
            line=12,
            severity=ReviewSeverity.BLOCKER,
            message=(
                "This timestamp creates a new idempotency key for every retry, so the "
                "payment provider can process the same logical capture more than once."
            ),
        ),
        ReviewCommentInput(
            file="apps/api/src/orders/finalize.ts",
            line=5,
            severity=ReviewSeverity.MAJOR,
            message=(
                "The order is marked paid before capture succeeds, so a provider failure "
                "leaves internal order state claiming money was collected when it was not."
            ),
        ),
        ReviewCommentInput(
            file="apps/api/src/webhooks/stripe.ts",
            line=6,
            severity=ReviewSeverity.BLOCKER,
            message=(
                "Removing signature verification lets an unauthenticated caller forge a "
                "payment success webhook and mutate payment state without Stripe proving it."
            ),
        ),
    ]

    grade = grade_review(
        "payments-retry-001",
        comments,
        ReviewVerdict.REQUEST_CHANGES,
    )

    assert grade.score == 100
    assert grade.recall == 1
    assert grade.precision == 1
    assert grade.severity_accuracy == 1
    assert grade.reasoning_quality == 1
    assert grade.verdict_correct is True
    assert len(grade.caught) == 3
    assert grade.missed == ()
    assert grade.false_positive_count == 0


def test_unknown_challenge_is_rejected_by_grader() -> None:
    with pytest.raises(ValueError, match="Unknown PR review challenge"):
        grade_review(
            "missing-challenge",
            [],
            ReviewVerdict.COMMENT,
        )
