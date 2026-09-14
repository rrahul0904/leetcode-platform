import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import {
  afterEach,
  beforeEach,
  describe,
  expect,
  it,
  vi,
} from "vitest";

import { PrReviewLab } from "./pr-review-lab";

const apiMocks = vi.hoisted(() => ({
  createReviewComment: vi.fn(),
  createReviewSession: vi.fn(),
  deleteReviewComment: vi.fn(),
  getReviewChallenge: vi.fn(),
  getReviewSession: vi.fn(),
  listReviewSessions: vi.fn(),
  submitReviewSession: vi.fn(),
}));

vi.mock("@/lib/pr-review-api", () => apiMocks);

const challenge = {
  id: "payments-retry-001",
  title: "Prevent duplicate checkout captures",
  repository: "commerce/payments-api",
  pullRequest: 418,
  author: "maya-chen",
  difficulty: "Senior",
  estimatedMinutes: 20,
  summary: "Review the payment capture retry change.",
  files: [
    {
      path: "apps/api/src/payments/capture.ts",
      additions: 1,
      deletions: 1,
      lines: [
        {
          oldLine: 11,
          newLine: null,
          kind: "deletion" as const,
          content: "  const idempotencyKey = order.id;",
        },
        {
          oldLine: null,
          newLine: 12,
          kind: "addition" as const,
          content: "  const idempotencyKey = `${order.id}-${Date.now()}`;",
        },
      ],
    },
  ],
};

const session = {
  id: "00000000-0000-0000-0000-000000000111",
  challengeId: challenge.id,
  status: "active" as const,
  verdict: null,
  score: null,
  recall: null,
  precision: null,
  severityAccuracy: null,
  reasoningQuality: null,
  verdictCorrect: null,
  startedAt: "2026-09-14T12:00:00Z",
  updatedAt: "2026-09-14T12:00:00Z",
  submittedAt: null,
};

const persistedComment = {
  id: "00000000-0000-0000-0000-000000000222",
  sessionId: session.id,
  file: "apps/api/src/payments/capture.ts",
  line: 12,
  severity: "blocker" as const,
  message:
    "The timestamp changes the idempotency key on every retry, so a retried capture can charge the customer twice.",
  createdAt: "2026-09-14T12:01:00Z",
};

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

beforeEach(() => {
  apiMocks.getReviewChallenge.mockResolvedValue(challenge);
  apiMocks.listReviewSessions.mockResolvedValue([]);
  apiMocks.createReviewSession.mockResolvedValue(session);
  apiMocks.createReviewComment.mockResolvedValue(persistedComment);
  apiMocks.submitReviewSession.mockResolvedValue({
    session: {
      ...session,
      status: "submitted",
      verdict: "request-changes",
      score: 50,
      submittedAt: "2026-09-14T12:02:00Z",
    },
    grade: {
      score: 50,
      caught: [
        {
          id: "unstable-idempotency-key",
          file: persistedComment.file,
          line: 12,
          severity: "blocker",
          title: "Retry idempotency is broken",
          explanation: "A retry gets a fresh key and can duplicate capture.",
        },
      ],
      missed: [
        {
          id: "paid-before-capture",
          file: "apps/api/src/orders/finalize.ts",
          line: 5,
          severity: "major",
          title: "Order state commits before payment succeeds",
          explanation: "Internal state can claim payment succeeded before capture.",
        },
        {
          id: "unsigned-webhook",
          file: "apps/api/src/webhooks/stripe.ts",
          line: 6,
          severity: "blocker",
          title: "Webhook signature verification was removed",
          explanation: "Unsigned callers can forge success events.",
        },
      ],
      falsePositiveCount: 0,
      severityAccuracy: 1,
      precision: 1,
      recall: 1 / 3,
      reasoningQuality: 1,
      verdictCorrect: true,
    },
  });
});

describe("PrReviewLab", () => {
  it("persists comments and receives grading from the server", async () => {
    render(<PrReviewLab />);

    expect(
      await screen.findByRole("heading", { name: "PR Review Lab" }),
    ).toBeInTheDocument();

    fireEvent.click(
      screen.getByRole("button", {
        name: "Review apps/api/src/payments/capture.ts line 12",
      }),
    );
    fireEvent.change(screen.getByRole("textbox", { name: "Review comment" }), {
      target: { value: persistedComment.message },
    });
    fireEvent.change(screen.getByLabelText("Severity"), {
      target: { value: "blocker" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Add comment" }));

    await waitFor(() => {
      expect(apiMocks.createReviewSession).toHaveBeenCalledWith(challenge.id);
      expect(apiMocks.createReviewComment).toHaveBeenCalledWith(
        session.id,
        expect.objectContaining({
          file: persistedComment.file,
          line: 12,
          severity: "blocker",
        }),
      );
    });

    fireEvent.click(screen.getByRole("button", { name: "Submit review" }));

    expect(await screen.findByText("Review scored server-side")).toBeInTheDocument();
    expect(screen.getByText(/1 of 3 findings caught/)).toBeInTheDocument();
    expect(screen.getByText("Retry idempotency is broken")).toBeInTheDocument();
    expect(apiMocks.submitReviewSession).toHaveBeenCalledWith(
      session.id,
      "request-changes",
    );
  });
});
