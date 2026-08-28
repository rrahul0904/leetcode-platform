import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { SkillsForgePracticeWorkspace } from "./skillsforge-practice-workspace";
import { QueryProvider } from "./query-provider";

const createRuntimePracticeSession = vi.fn();
const getExecutionCapability = vi.fn();

vi.mock("@/lib/execution-capability", () => ({
  getExecutionCapability: (...args: unknown[]) => getExecutionCapability(...args),
}));

vi.mock("@/lib/async-execution", () => ({
  cancelExecution: vi.fn(),
  createRuntimePracticeSession: (...args: unknown[]) =>
    createRuntimePracticeSession(...args),
  getCompletedSubmission: vi.fn(),
  getExecution: vi.fn(),
  isTerminalExecution: (status: string) =>
    ["COMPLETED", "FAILED", "TIMEOUT", "CANCELLED"].includes(status),
  queueRunExecution: vi.fn(),
  queueSubmitExecution: vi.fn(),
}));

vi.mock("@/lib/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api")>()),
  autosavePracticeSession: vi.fn(),
  getPublishedQuestion: () =>
    Promise.resolve({
      external_id: "SF-001",
      title: "Reliable Event Aggregation",
      slug: "reliable-event-aggregation",
      track: "data-engineering",
      difficulty: "intermediate",
      role_level: "senior",
      estimated_duration_minutes: 35,
      publication_version: 1,
      problem_statement: "Aggregate the events correctly.",
      learning_objectives: ["Build a reliable aggregation."],
      prerequisites: [],
      candidate_instructions: ["Return the requested result."],
      public_constraints: ["Do not mutate production data."],
      public_examples: [],
      skills: ["sql"],
      company_style_tags: [],
      starter_code: null,
    }),
  revealPracticeHint: vi.fn(),
}));

function renderWorkspace() {
  return render(
    <QueryProvider>
      <SkillsForgePracticeWorkspace slug="reliable-event-aggregation" />
    </QueryProvider>,
  );
}

afterEach(() => {
  vi.clearAllMocks();
});

describe("SkillsForgePracticeWorkspace", () => {
  it("does not create a practice session for hosted-only content", async () => {
    getExecutionCapability.mockResolvedValue({
      question_version_id: "00000000-0000-0000-0000-000000000001",
      availability: "hosted",
      runtime: null,
      starter_source: "",
      public_test_count: 0,
      hidden_test_count: 0,
      reason: "No deterministic execution tests are published for this question version.",
    });

    renderWorkspace();

    expect(
      await screen.findByRole("heading", { name: "This question is not runnable yet." }),
    ).toBeInTheDocument();
    expect(createRuntimePracticeSession).not.toHaveBeenCalled();
    expect(screen.queryByRole("button", { name: /run public tests/i })).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /submit for evaluation/i }),
    ).not.toBeInTheDocument();
  });

  it("uses the exact PostgreSQL runtime returned by the server", async () => {
    getExecutionCapability.mockResolvedValue({
      question_version_id: "00000000-0000-0000-0000-000000000002",
      availability: "runnable",
      runtime: "postgresql18",
      starter_source: "SELECT 1;\n",
      public_test_count: 1,
      hidden_test_count: 1,
      reason: null,
    });
    createRuntimePracticeSession.mockResolvedValue({
      id: "00000000-0000-0000-0000-000000000010",
      state: "IN_PROGRESS",
      question_slug: "reliable-event-aggregation",
      runtime: "postgresql18",
      draft_code: "SELECT 1;\n",
      elapsed_seconds: 0,
      hints_revealed: 0,
      created_at: "2026-08-28T00:00:00Z",
      updated_at: "2026-08-28T00:00:00Z",
    });

    renderWorkspace();

    await waitFor(() =>
      expect(createRuntimePracticeSession).toHaveBeenCalledWith(
        "reliable-event-aggregation",
        "postgresql18",
      ),
    );
    expect(await screen.findByText(/PostgreSQL 18/)).toBeInTheDocument();
  });
});
