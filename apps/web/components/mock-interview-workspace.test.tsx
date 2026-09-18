import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { MockInterviewWorkspace } from "./mock-interview-workspace";

const apiMocks = vi.hoisted(() => ({
  answerMockInterview: vi.fn(),
  createMockInterview: vi.fn(),
  getMockInterview: vi.fn(),
  getMockInterviewTemplates: vi.fn(),
  listMockInterviews: vi.fn(),
  updateMockInterviewState: vi.fn(),
}));

vi.mock("@/lib/mock-interview-api", () => apiMocks);

const template = {
  slug: "data-engineering",
  label: "Data engineering",
  description: "Design a production data platform.",
  competencies: ["data-architecture", "distributed-systems"],
  phases: [
    { slug: "problem-framing", label: "Problem framing" },
    { slug: "trade-offs", label: "Trade-offs" },
  ],
};

const activeSession = {
  id: "00000000-0000-0000-0000-000000000401",
  interview_type: "TECHNICAL_MOCK",
  target_role: "Senior Data Engineer",
  focus: "data-engineering",
  focus_label: "Data engineering",
  status: "IN_PROGRESS" as const,
  current_phase: "problem-framing",
  started_at: "2026-09-18T04:00:00Z",
  completed_at: null,
  created_at: "2026-09-18T04:00:00Z",
  updated_at: "2026-09-18T04:00:00Z",
  messages: [
    {
      id: "00000000-0000-0000-0000-000000000402",
      session_id: "00000000-0000-0000-0000-000000000401",
      sequence_number: 0,
      role: "interviewer",
      phase: "problem-framing",
      content: "Clarify the requirements before choosing an architecture.",
      evidence: {},
      created_at: "2026-09-18T04:00:00Z",
    },
  ],
  report: null,
};

const completedSession = {
  ...activeSession,
  status: "COMPLETED" as const,
  current_phase: "COMPLETE",
  completed_at: "2026-09-18T04:10:00Z",
  messages: [
    ...activeSession.messages,
    {
      id: "00000000-0000-0000-0000-000000000403",
      session_id: activeSession.id,
      sequence_number: 1,
      role: "candidate",
      phase: "problem-framing",
      content: "I would quantify volume, latency, sources, and quality contracts.",
      evidence: { score: 0.82 },
      created_at: "2026-09-18T04:02:00Z",
    },
  ],
  report: {
    overall_score: 0.82,
    rubric_evidence: [],
    strengths: ["Problem framing was evidence-rich."],
    growth_areas: ["Make cost trade-offs more explicit."],
    next_steps: ["Rehearse the trade-off phase."],
  },
};

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

beforeEach(() => {
  apiMocks.getMockInterviewTemplates.mockResolvedValue([template]);
  apiMocks.listMockInterviews.mockResolvedValue([]);
  apiMocks.createMockInterview.mockResolvedValue(activeSession);
  apiMocks.answerMockInterview.mockResolvedValue(completedSession);
  apiMocks.updateMockInterviewState.mockResolvedValue(activeSession);
  apiMocks.getMockInterview.mockResolvedValue(activeSession);
});

describe("MockInterviewWorkspace", () => {
  it("starts a persisted interview and renders the server report", async () => {
    render(<MockInterviewWorkspace />);

    expect(
      await screen.findByRole("heading", {
        name: "Practice the conversation, not just the answer.",
      }),
    ).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /start interview/i }));

    expect(
      await screen.findByText("Clarify the requirements before choosing an architecture."),
    ).toBeInTheDocument();
    expect(apiMocks.createMockInterview).toHaveBeenCalledWith(
      "data-engineering",
      "Senior Data Engineer",
      expect.any(String),
    );

    fireEvent.change(
      screen.getByPlaceholderText(/answer as if you were speaking to the interviewer/i),
      {
        target: {
          value: "I would quantify volume, latency, sources, and quality contracts.",
        },
      },
    );
    fireEvent.click(screen.getByRole("button", { name: /submit response/i }));

    expect(await screen.findByText("Your evidence report")).toBeInTheDocument();
    expect(screen.getByText("82")).toBeInTheDocument();
    expect(screen.getByText("Problem framing was evidence-rich.")).toBeInTheDocument();
    expect(apiMocks.answerMockInterview).toHaveBeenCalledWith(
      activeSession.id,
      "I would quantify volume, latency, sources, and quality contracts.",
      expect.any(String),
    );
  });

  it("opens a candidate-owned persisted session from history", async () => {
    apiMocks.listMockInterviews.mockResolvedValue([
      {
        id: activeSession.id,
        interview_type: activeSession.interview_type,
        target_role: activeSession.target_role,
        focus: activeSession.focus,
        focus_label: activeSession.focus_label,
        status: activeSession.status,
        current_phase: activeSession.current_phase,
        started_at: activeSession.started_at,
        completed_at: activeSession.completed_at,
        created_at: activeSession.created_at,
        updated_at: activeSession.updated_at,
      },
    ]);

    render(<MockInterviewWorkspace />);

    const historyButton = await screen.findByRole("button", {
      name: /Data engineering.*IN PROGRESS.*Senior Data Engineer/i,
    });
    fireEvent.click(historyButton);

    await waitFor(() => {
      expect(apiMocks.getMockInterview).toHaveBeenCalledWith(activeSession.id);
    });
    expect(
      await screen.findByText("Clarify the requirements before choosing an architecture."),
    ).toBeInTheDocument();
  });
});
