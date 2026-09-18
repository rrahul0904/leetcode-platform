from __future__ import annotations

import pytest

import rigor_api.pr_review_domain as pr_review


def test_public_challenge_does_not_expose_hidden_findings() -> None:
    challenge = pr_review.get_public_challenge("payments-retry-001")

    assert challenge is not None
    payload = challenge.model_dump(mode="json")
    assert payload["id"] == "payments-retry-001"
    assert "findings" not in payload
    assert "gold_findings" not in payload
    assert len(payload["files"]) == 3


def test_review_location_must_target_a_known_diff_line() -> None:
    assert pr_review.review_location_is_valid(
        "payments-retry-001",
        "apps/api/src/payments/capture.ts",
        12,
    )
    assert not pr_review.review_location_is_valid(
        "payments-retry-001",
        "apps/api/src/payments/capture.ts",
        999,
    )
    assert not pr_review.review_location_is_valid(
        "missing-challenge",
        "apps/api/src/payments/capture.ts",
        12,
    )


def test_complete_review_receives_full_deterministic_score() -> None:
    comments = [
        pr_review.ReviewCommentInput(
            file="apps/api/src/payments/capture.ts",
            line=12,
            severity=pr_review.ReviewSeverity.BLOCKER,
            message=(
                "This timestamp creates a new idempotency key for every retry, so the "
                "payment provider can process the same logical capture more than once."
            ),
        ),
        pr_review.ReviewCommentInput(
            file="apps/api/src/orders/finalize.ts",
            line=5,
            severity=pr_review.ReviewSeverity.MAJOR,
            message=(
                "The order is marked paid before capture succeeds, so a provider failure "
                "leaves internal order state claiming money was collected when it was not."
            ),
        ),
        pr_review.ReviewCommentInput(
            file="apps/api/src/webhooks/stripe.ts",
            line=6,
            severity=pr_review.ReviewSeverity.BLOCKER,
            message=(
                "Removing signature verification lets an unauthenticated caller forge a "
                "payment success webhook and mutate payment state without Stripe proving it."
            ),
        ),
    ]

    grade = pr_review.grade_review(
        "payments-retry-001",
        comments,
        pr_review.ReviewVerdict.REQUEST_CHANGES,
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
        pr_review.grade_review(
            "missing-challenge",
            [],
            pr_review.ReviewVerdict.COMMENT,
        )
