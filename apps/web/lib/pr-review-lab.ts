export type ReviewSeverity = "info" | "minor" | "major" | "blocker";
export type ReviewVerdict = "approve" | "comment" | "request-changes";
export type DiffLineKind = "context" | "addition" | "deletion";

export type DiffLine = {
  oldLine: number | null;
  newLine: number | null;
  kind: DiffLineKind;
  content: string;
};

export type ReviewFile = {
  path: string;
  additions: number;
  deletions: number;
  lines: DiffLine[];
};

export type ReviewComment = {
  id: string;
  file: string;
  line: number;
  severity: ReviewSeverity;
  message: string;
};

type GoldFinding = {
  id: string;
  file: string;
  line: number;
  severity: ReviewSeverity;
  title: string;
  explanation: string;
};

export type ReviewGrade = {
  score: number;
  caught: GoldFinding[];
  missed: GoldFinding[];
  falsePositives: ReviewComment[];
  severityAccuracy: number;
  precision: number;
  recall: number;
  verdictCorrect: boolean;
};

export const reviewChallenge = {
  id: "payments-retry-001",
  title: "Prevent duplicate checkout captures",
  repository: "commerce/payments-api",
  pullRequest: 418,
  author: "maya-chen",
  difficulty: "Senior",
  estimatedMinutes: 20,
  summary:
    "A checkout reliability patch adds retry handling around payment capture. Review the diff for correctness, data consistency, and security before it ships.",
  files: [
    {
      path: "apps/api/src/payments/capture.ts",
      additions: 7,
      deletions: 2,
      lines: [
        { oldLine: 8, newLine: 8, kind: "context", content: "export async function capture(order: Order) {" },
        { oldLine: 9, newLine: 9, kind: "context", content: "  const payment = await payments.findByOrder(order.id);" },
        { oldLine: null, newLine: 10, kind: "addition", content: "  if (payment?.status === \"succeeded\") return payment;" },
        { oldLine: 10, newLine: 11, kind: "context", content: "" },
        { oldLine: 11, newLine: null, kind: "deletion", content: "  const idempotencyKey = order.id;" },
        { oldLine: null, newLine: 12, kind: "addition", content: "  const idempotencyKey = `${order.id}-${Date.now()}`;" },
        { oldLine: 12, newLine: 13, kind: "context", content: "  return stripe.paymentIntents.capture(payment.intentId, {" },
        { oldLine: 13, newLine: 14, kind: "context", content: "    idempotencyKey," },
        { oldLine: 14, newLine: 15, kind: "context", content: "  });" },
      ],
    },
    {
      path: "apps/api/src/orders/finalize.ts",
      additions: 4,
      deletions: 1,
      lines: [
        { oldLine: 4, newLine: 4, kind: "context", content: "export async function finalizeOrder(order: Order) {" },
        { oldLine: null, newLine: 5, kind: "addition", content: "  await orders.update(order.id, { status: \"paid\" });" },
        { oldLine: 5, newLine: 6, kind: "context", content: "" },
        { oldLine: 6, newLine: 7, kind: "context", content: "  const payment = await capture(order);" },
        { oldLine: 7, newLine: null, kind: "deletion", content: "  await orders.update(order.id, { status: \"paid\" });" },
        { oldLine: null, newLine: 8, kind: "addition", content: "  return { orderId: order.id, paymentId: payment.id };" },
      ],
    },
    {
      path: "apps/api/src/webhooks/stripe.ts",
      additions: 5,
      deletions: 1,
      lines: [
        { oldLine: 5, newLine: 5, kind: "context", content: "export async function handleStripeWebhook(req: Request) {" },
        { oldLine: 6, newLine: null, kind: "deletion", content: "  const event = verifyStripeEvent(req);" },
        { oldLine: null, newLine: 6, kind: "addition", content: "  const event = await req.json();" },
        { oldLine: 7, newLine: 7, kind: "context", content: "  if (event.type === \"payment_intent.succeeded\") {" },
        { oldLine: 8, newLine: 8, kind: "context", content: "    await payments.markSucceeded(event.data.object.id);" },
        { oldLine: 9, newLine: 9, kind: "context", content: "  }" },
      ],
    },
  ] satisfies ReviewFile[],
};

const goldFindings: GoldFinding[] = [
  {
    id: "unstable-idempotency-key",
    file: "apps/api/src/payments/capture.ts",
    line: 12,
    severity: "blocker",
    title: "Retry idempotency is broken",
    explanation:
      "Appending the current timestamp creates a new idempotency key for every retry, so the provider can process duplicate captures.",
  },
  {
    id: "paid-before-capture",
    file: "apps/api/src/orders/finalize.ts",
    line: 5,
    severity: "major",
    title: "Order state commits before payment succeeds",
    explanation:
      "The order is marked paid before capture returns. A provider failure leaves internal state claiming payment succeeded.",
  },
  {
    id: "unsigned-webhook",
    file: "apps/api/src/webhooks/stripe.ts",
    line: 6,
    severity: "blocker",
    title: "Webhook signature verification was removed",
    explanation:
      "Parsing request JSON directly allows an unauthenticated caller to forge payment success events.",
  },
];

const severityRank: Record<ReviewSeverity, number> = {
  info: 0,
  minor: 1,
  major: 2,
  blocker: 3,
};

function matchingFinding(comment: ReviewComment, available: GoldFinding[]) {
  return available
    .filter((finding) => finding.file === comment.file && Math.abs(finding.line - comment.line) <= 1)
    .sort((a, b) => Math.abs(a.line - comment.line) - Math.abs(b.line - comment.line))[0];
}

export function gradeReview(
  comments: ReviewComment[],
  verdict: ReviewVerdict,
): ReviewGrade {
  const unmatched = [...goldFindings];
  const caught: GoldFinding[] = [];
  const matchedComments: Array<{ comment: ReviewComment; finding: GoldFinding }> = [];
  const falsePositives: ReviewComment[] = [];

  for (const comment of comments) {
    const finding = matchingFinding(comment, unmatched);
    if (!finding) {
      falsePositives.push(comment);
      continue;
    }

    caught.push(finding);
    matchedComments.push({ comment, finding });
    unmatched.splice(unmatched.findIndex((item) => item.id === finding.id), 1);
  }

  const recall = caught.length / goldFindings.length;
  const precision = comments.length === 0 ? 0 : caught.length / comments.length;
  const severityAccuracy =
    matchedComments.length === 0
      ? 0
      : matchedComments.filter(
          ({ comment, finding }) => severityRank[comment.severity] === severityRank[finding.severity],
        ).length / matchedComments.length;
  const reasoningQuality =
    comments.length === 0
      ? 0
      : comments.reduce((sum, comment) => sum + Math.min(comment.message.trim().length / 80, 1), 0) /
        comments.length;
  const verdictCorrect = verdict === "request-changes";

  const score = Math.round(
    recall * 50 +
      precision * 20 +
      severityAccuracy * 15 +
      reasoningQuality * 10 +
      (verdictCorrect ? 5 : 0),
  );

  return {
    score,
    caught,
    missed: unmatched,
    falsePositives,
    severityAccuracy,
    precision,
    recall,
    verdictCorrect,
  };
}
