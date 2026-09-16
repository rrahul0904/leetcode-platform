import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { QueryProvider } from "./query-provider";

const getPublishedQuestion = vi.fn();

vi.mock("@/lib/api", () => ({
  getPublishedQuestion: (...args: unknown[]) => getPublishedQuestion(...args),
}));

vi.mock("@/components/skillsforge-practice-workspace", () => ({
  SkillsForgePracticeWorkspace: ({ slug }: { slug: string }) => (
    <div>Practice workspace: {slug}</div>
  ),
}));

vi.mock("@/components/tutor-dock", () => ({
  TutorDock: ({ slug }: { slug: string }) => <div>Tutor dock: {slug}</div>,
}));

import { GuidedPracticeExperience } from "./guided-practice-experience";

afterEach(() => {
  window.localStorage.clear();
  vi.clearAllMocks();
});

describe("GuidedPracticeExperience", () => {
  it("adds the guided journey without replacing the existing workspace or tutor", async () => {
    getPublishedQuestion.mockResolvedValue({
      external_id: "SF-001",
      title: "Reliable Event Aggregation",
      slug: "reliable-event-aggregation",
      track: "data-engineering",
      difficulty: "intermediate",
      role_level: "senior",
      estimated_duration_minutes: 35,
      publication_version: 1,
      problem_statement: "Aggregate the events correctly.",
      learning_objectives: ["Choose a reliable aggregation strategy."],
      prerequisites: [],
      candidate_instructions: ["Return the requested result."],
      public_constraints: ["Handle duplicate events safely."],
      public_examples: [],
      skills: ["sql"],
      company_style_tags: [],
      starter_code: null,
    });

    render(
      <QueryProvider>
        <GuidedPracticeExperience slug="reliable-event-aggregation" />
      </QueryProvider>,
    );

    expect(await screen.findByRole("region", { name: "Guided practice journey" })).toBeInTheDocument();
    expect(screen.getByText("Practice workspace: reliable-event-aggregation")).toBeInTheDocument();
    expect(screen.getByText("Tutor dock: reliable-event-aggregation")).toBeInTheDocument();
    expect(screen.getByText("Choose a reliable aggregation strategy.")).toBeInTheDocument();
  });
});
