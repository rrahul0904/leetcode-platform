from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class ReviewModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ReviewSeverity(StrEnum):
    INFO = "info"
    MINOR = "minor"
    MAJOR = "major"
    BLOCKER = "blocker"


class ReviewVerdict(StrEnum):
    APPROVE = "approve"
    COMMENT = "comment"
    REQUEST_CHANGES = "request-changes"


class DiffLine(ReviewModel):
    old_line: int | None = Field(default=None, gt=0)
    new_line: int | None = Field(default=None, gt=0)
    kind: str
    content: str


class ReviewFile(ReviewModel):
    path: str = Field(min_length=1, max_length=500)
    additions: int = Field(ge=0)
    deletions: int = Field(ge=0)
    lines: tuple[DiffLine, ...]


class PublicReviewChallenge(ReviewModel):
    id: str
    title: str
    repository: str
    pull_request: int = Field(gt=0)
    author: str
    difficulty: str
    estimated_minutes: int = Field(gt=0)
    summary: str
    files: tuple[ReviewFile, ...]


class ReviewCommentInput(ReviewModel):
    file: str = Field(min_length=1, max_length=500)
    line: int = Field(gt=0)
    severity: ReviewSeverity
    message: str = Field(min_length=1, max_length=4000)


class GradedFinding(ReviewModel):
    id: str
    file: str
    line: int
    severity: ReviewSeverity
    title: str
    explanation: str


class ReviewGrade(ReviewModel):
    score: int = Field(ge=0, le=100)
    caught: tuple[GradedFinding, ...]
    missed: tuple[GradedFinding, ...]
    false_positive_count: int = Field(ge=0)
    severity_accuracy: float = Field(ge=0, le=1)
    precision: float = Field(ge=0, le=1)
    recall: float = Field(ge=0, le=1)
    reasoning_quality: float = Field(ge=0, le=1)
    verdict_correct: bool


class _ChallengeSpec(ReviewModel):
    public: PublicReviewChallenge
    findings: tuple[GradedFinding, ...]


def _line(
    old_line: int | None,
    new_line: int | None,
    kind: str,
    content: str,
) -> DiffLine:
    return DiffLine(
        old_line=old_line,
        new_line=new_line,
        kind=kind,
        content=content,
    )


_PAYMENTS_RETRY = _ChallengeSpec(
    public=PublicReviewChallenge(
        id="payments-retry-001",
        title="Prevent duplicate checkout captures",
        repository="commerce/payments-api",
        pull_request=418,
        author="maya-chen",
        difficulty="Senior",
        estimated_minutes=20,
        summary=(
            "A checkout reliability patch adds retry handling around payment capture. "
            "Review the diff for correctness, data consistency, and security before it ships."
        ),
        files=(
            ReviewFile(
                path="apps/api/src/payments/capture.ts",
                additions=7,
                deletions=2,
                lines=(
                    _line(
                        8,
                        8,
                        "context",
                        "export async function capture(order: Order) {",
                    ),
                    _line(
                        9,
                        9,
                        "context",
                        "  const payment = await payments.findByOrder(order.id);",
                    ),
                    _line(
                        None,
                        10,
                        "addition",
                        '  if (payment?.status === "succeeded") return payment;',
                    ),
                    _line(10, 11, "context", ""),
                    _line(
                        11,
                        None,
                        "deletion",
                        "  const idempotencyKey = order.id;",
                    ),
                    _line(
                        None,
                        12,
                        "addition",
                        "  const idempotencyKey = `${order.id}-${Date.now()}`;",
                    ),
                    _line(
                        12,
                        13,
                        "context",
                        "  return stripe.paymentIntents.capture(payment.intentId, {",
                    ),
                    _line(13, 14, "context", "    idempotencyKey,"),
                    _line(14, 15, "context", "  });"),
                ),
            ),
            ReviewFile(
                path="apps/api/src/orders/finalize.ts",
                additions=4,
                deletions=1,
                lines=(
                    _line(
                        4,
                        4,
                        "context",
                        "export async function finalizeOrder(order: Order) {",
                    ),
                    _line(
                        None,
                        5,
                        "addition",
                        '  await orders.update(order.id, { status: "paid" });',
                    ),
                    _line(5, 6, "context", ""),
                    _line(
                        6,
                        7,
                        "context",
                        "  const payment = await capture(order);",
                    ),
                    _line(
                        7,
                        None,
                        "deletion",
                        '  await orders.update(order.id, { status: "paid" });',
                    ),
                    _line(
                        None,
                        8,
                        "addition",
                        "  return { orderId: order.id, paymentId: payment.id };",
                    ),
                ),
            ),
            ReviewFile(
                path="apps/api/src/webhooks/stripe.ts",
                additions=5,
                deletions=1,
                lines=(
                    _line(
                        5,
                        5,
                        "context",
                        "export async function handleStripeWebhook(req: Request) {",
                    ),
                    _line(
                        6,
                        None,
                        "deletion",
                        "  const event = verifyStripeEvent(req);",
                    ),
                    _line(
                        None,
                        6,
                        "addition",
                        "  const event = await req.json();",
                    ),
                    _line(
                        7,
                        7,
                        "context",
                        '  if (event.type === "payment_intent.succeeded") {',
                    ),
                    _line(
                        8,
                        8,
                        "context",
                        "    await payments.markSucceeded(event.data.object.id);",
                    ),
                    _line(9, 9, "context", "  }"),
                ),
            ),
        ),
    ),
    findings=(
        GradedFinding(
            id="unstable-idempotency-key",
            file="apps/api/src/payments/capture.ts",
            line=12,
            severity=ReviewSeverity.BLOCKER,
            title="Retry idempotency is broken",
            explanation=(
                "Appending the current timestamp creates a new idempotency key for every "
                "retry, so the provider can process duplicate captures."
            ),
        ),
        GradedFinding(
            id="paid-before-capture",
            file="apps/api/src/orders/finalize.ts",
            line=5,
            severity=ReviewSeverity.MAJOR,
            title="Order state commits before payment succeeds",
            explanation=(
                "The order is marked paid before capture returns. A provider failure leaves "
                "internal state claiming payment succeeded."
            ),
        ),
        GradedFinding(
            id="unsigned-webhook",
            file="apps/api/src/webhooks/stripe.ts",
            line=6,
            severity=ReviewSeverity.BLOCKER,
            title="Webhook signature verification was removed",
            explanation=(
                "Parsing request JSON directly allows an unauthenticated caller to forge "
                "payment success events."
            ),
        ),
    ),
)

_CHALLENGES: dict[str, _ChallengeSpec] = {
    _PAYMENTS_RETRY.public.id: _PAYMENTS_RETRY,
}

_SEVERITY_RANK = {
    ReviewSeverity.INFO: 0,
    ReviewSeverity.MINOR: 1,
    ReviewSeverity.MAJOR: 2,
    ReviewSeverity.BLOCKER: 3,
}


def get_public_challenge(challenge_id: str) -> PublicReviewChallenge | None:
    spec = _CHALLENGES.get(challenge_id)
    return spec.public if spec else None


def review_location_is_valid(
    challenge_id: str,
    file_path: str,
    line_number: int,
) -> bool:
    challenge = get_public_challenge(challenge_id)
    if challenge is None:
        return False
    for review_file in challenge.files:
        if review_file.path != file_path:
            continue
        return any(
            (line.new_line if line.new_line is not None else line.old_line) == line_number
            for line in review_file.lines
        )
    return False


def _matching_finding(
    comment: ReviewCommentInput,
    available: list[GradedFinding],
) -> GradedFinding | None:
    candidates = [
        finding
        for finding in available
        if finding.file == comment.file and abs(finding.line - comment.line) <= 1
    ]
    if not candidates:
        return None
    return min(
        candidates,
        key=lambda finding: abs(finding.line - comment.line),
    )


def grade_review(
    challenge_id: str,
    comments: list[ReviewCommentInput],
    verdict: ReviewVerdict,
) -> ReviewGrade:
    spec = _CHALLENGES.get(challenge_id)
    if spec is None:
        raise ValueError("Unknown PR review challenge")

    unmatched = list(spec.findings)
    caught: list[GradedFinding] = []
    matched: list[tuple[ReviewCommentInput, GradedFinding]] = []
    false_positive_count = 0

    for comment in comments:
        finding = _matching_finding(comment, unmatched)
        if finding is None:
            false_positive_count += 1
            continue
        caught.append(finding)
        matched.append((comment, finding))
        unmatched.remove(finding)

    recall = len(caught) / len(spec.findings)
    precision = len(caught) / len(comments) if comments else 0.0
    severity_accuracy = (
        sum(
            1
            for comment, finding in matched
            if _SEVERITY_RANK[comment.severity] == _SEVERITY_RANK[finding.severity]
        )
        / len(matched)
        if matched
        else 0.0
    )
    reasoning_quality = (
        sum(
            min(len(comment.message.strip()) / 80, 1.0)
            for comment in comments
        )
        / len(comments)
        if comments
        else 0.0
    )
    verdict_correct = verdict is ReviewVerdict.REQUEST_CHANGES
    score = round(
        recall * 50
        + precision * 20
        + severity_accuracy * 15
        + reasoning_quality * 10
        + (5 if verdict_correct else 0)
    )

    return ReviewGrade(
        score=score,
        caught=tuple(caught),
        missed=tuple(unmatched),
        false_positive_count=false_positive_count,
        severity_accuracy=severity_accuracy,
        precision=precision,
        recall=recall,
        reasoning_quality=reasoning_quality,
        verdict_correct=verdict_correct,
    )
