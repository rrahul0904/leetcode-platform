import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { AttemptHistory } from "./attempt-history";

const apiMocks = vi.hoisted(() => ({
  getSubmissions: vi.fn(),
}));

vi.mock("@/lib/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api")>()),
  getSubmissions: apiMocks.getSubmissions,
}));

function renderHistory() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <AttemptHistory />
    </QueryClientProvider>,
  );
}

describe("AttemptHistory", () => {
  it("renders persisted submission evidence", async () => {
    apiMocks.getSubmissions.mockResolvedValue([
      {
        id: "00000000-0000-0000-0000-000000000501",
        practice_session_id: "00000000-0000-0000-0000-000000000502",
        question_version_id: "00000000-0000-0000-0000-000000000503",
        question_slug: "bounded-cache",
        question_title: "Bounded cache",
        publication_version: "1.0.0",
        runtime: "python",
        source_code: "def solve(): pass",
        status: "passed",
        execution: {
          execution_request_id: "00000000-0000-0000-0000-000000000504",
          submission_id: "00000000-0000-0000-0000-000000000501",
          state: "COMPLETED",
          public_results: [
            {
              test_id: "p1",
              name: "public",
              passed: true,
              expected: null,
              actual: null,
              duration_ms: 1,
            },
          ],
          hidden_total: 2,
          hidden_passed: 2,
          runtime_ms: 42,
          memory_kb: 1024,
          error_category: null,
          candidate_message: null,
          quality_signals: {},
        },
        evaluation: {
          correctness_score: 1,
          complexity_score: 0.9,
          code_quality_score: 0.8,
          testing_score: 0.9,
          robustness_score: 0.85,
          overall_score: 0.89,
          evaluator_version: "test",
          deterministic_signals: {},
          heuristic_signals: {},
          created_at: "2026-09-18T04:00:00Z",
        },
        submitted_at: "2026-09-18T04:00:00Z",
        completed_at: "2026-09-18T04:01:00Z",
      },
    ]);

    renderHistory();

    expect(await screen.findByText("Bounded cache")).toBeInTheDocument();
    expect(screen.getByText("89")).toBeInTheDocument();
    expect(screen.getByText("3/3")).toBeInTheDocument();
    expect(screen.getByText("42ms")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /revisit question/i })).toHaveAttribute(
      "href",
      "/questions/bounded-cache",
    );
  });
});
