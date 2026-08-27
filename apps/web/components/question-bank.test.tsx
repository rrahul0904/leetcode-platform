import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { QueryProvider } from "./query-provider";
import { QuestionBank } from "./question-bank";

vi.mock("@/lib/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api")>()),
  getPublishedQuestions: () =>
    Promise.resolve({
      items: [
        {
          external_id: "PY-0005",
          title: "Select a Bounded Priority Worker Batch",
          slug: "py-0005-select-a-bounded-priority-worker-batch",
          track: "python-engineering",
          difficulty: "advanced",
          role_level: "senior",
          estimated_duration_minutes: 35,
          publication_version: "1.0.0",
          learning_objectives: [
            "Translate a production scenario into invariants.",
          ],
          skills: ["reliability", "algorithms"],
          company_style_tags: ["independent-production-interview"],
        },
      ],
      page: 1,
      page_size: 12,
      total: 1,
      has_next: false,
    }),
  getExternalReferenceFacets: () =>
    Promise.resolve({ sources: [], difficulties: [], competencies: [] }),
  getExternalReferences: () =>
    Promise.resolve({
      items: [],
      page: 1,
      page_size: 12,
      total: 0,
      has_next: false,
    }),
}));

describe("QuestionBank", () => {
  it("renders unified practice navigation and hosted capabilities", async () => {
    render(
      <QueryProvider>
        <QuestionBank />
      </QueryProvider>,
    );

    expect(
      await screen.findByText("Select a Bounded Priority Worker Batch"),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("tab", { name: "All practice" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("tab", { name: "Hosted questions" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("tab", { name: "External practice" }),
    ).toBeInTheDocument();
    expect(screen.queryByRole("tab", { name: "Simulations" })).not.toBeInTheDocument();
    expect(
      screen.getByRole("tab", { name: "Mock Interviews" }),
    ).toHaveAttribute("href", "/mock-interviews");
    expect(screen.getByRole("tab", { name: "Lessons" })).toHaveAttribute(
      "href",
      "/learning-paths",
    );
    expect(
      screen.getByText("Hosted prompt · Workspace ready"),
    ).toBeInTheDocument();
    expect(screen.getByText("Senior")).toBeInTheDocument();
  });
});
