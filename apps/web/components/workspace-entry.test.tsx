import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { QueryProvider } from "./query-provider";
import { WorkspaceEntry } from "./workspace-entry";

vi.mock("@/lib/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api")>()),
  getPublishedQuestions: () =>
    Promise.resolve({
      items: [
        {
          external_id: "PY-0001",
          title: "Build a Bounded TTL-Aware LRU Cache",
          slug: "py-0001-bounded-cache",
          track: "python-engineering",
          difficulty: "advanced",
          role_level: "senior",
          estimated_duration_minutes: 45,
          publication_version: "1.0.0",
          learning_objectives: ["Preserve bounded-cache invariants under expiry."],
          skills: ["caching", "data structures"],
          company_style_tags: [],
          completion_status: "not_started",
        },
      ],
      page: 1,
      page_size: 1,
      total: 1,
      has_next: false,
    }),
}));

describe("WorkspaceEntry", () => {
  it("opens a real published question in the isolated workspace", async () => {
    render(
      <QueryProvider>
        <WorkspaceEntry />
      </QueryProvider>,
    );

    expect(
      await screen.findByText("Build a Bounded TTL-Aware LRU Cache"),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: /open isolated workspace/i }),
    ).toHaveAttribute("href", "/practice/py-0001-bounded-cache");
  });
});
