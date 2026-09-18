import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { Dashboard } from "./dashboard";
import { QueryProvider } from "./query-provider";

vi.mock("@/lib/auth", () => ({
  useAuth: () => ({
    principal: {
      display_name: "Casey Candidate",
      email: "candidate@skillsforge.test",
      roles: ["candidate"],
    },
  }),
}));

vi.mock("@/lib/api", () => ({
  ApiError: class ApiError extends Error {
    constructor(public status: number, message: string) {
      super(message);
    }
  },
  getProfile: vi.fn().mockResolvedValue({
    target_roles: ["Data engineer"],
    target_companies: [],
    experience_level: "senior",
    preferred_programming_language: "python",
    weekly_study_hours: 6,
    interview_date: null,
    strong_areas: [],
    weak_areas: [],
    preparation_intensity: "focused",
  }),
  getCandidateReadiness: vi.fn().mockResolvedValue({
    target_role: "Data engineer",
    overall: { score: 0, confidence: 0 },
    evidence_count: 0,
    competencies: [],
    critical_gaps: [],
    strongest_areas: [],
    calculated_at: null,
  }),
  getCandidateCompetencies: vi.fn().mockResolvedValue([]),
  getSubmissions: vi.fn().mockResolvedValue([]),
  getNextAction: vi.fn().mockResolvedValue(null),
  getPublishedQuestions: vi.fn().mockResolvedValue({
    items: [],
    page: 1,
    page_size: 4,
    total: 0,
    pages: 0,
  }),
}));

describe("Dashboard", () => {
  it("shows honest evidence-driven candidate readiness", async () => {
    render(
      <QueryProvider>
        <Dashboard />
      </QueryProvider>,
    );

    expect(await screen.findByText("Welcome back, Casey.")).toBeInTheDocument();
    expect(screen.getByText("OVERALL READINESS")).toBeInTheDocument();
    expect(
      screen.getByText(/No evidence yet\. Complete a deterministic submission/i),
    ).toBeInTheDocument();
    expect(screen.getByText("Submissions")).toBeInTheDocument();
    expect(screen.getByText("Skills with evidence")).toBeInTheDocument();
    expect(screen.getByText("Recently published practice")).toBeInTheDocument();
  });
});
