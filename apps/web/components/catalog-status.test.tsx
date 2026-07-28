import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { CatalogStatus } from "./catalog-status";
import { QueryProvider } from "./query-provider";

vi.mock("@/lib/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api")>()),
  getCatalogStatus: () =>
    Promise.resolve([
      {
        source_id: "source-1",
        source_name: "Exercism",
        canonical_domain: "exercism.org",
        connector_status: "approved",
        last_run: "2026-07-21T16:00:00Z",
        references_collected: 1127,
        references_updated: 0,
        failures: 0,
        rights_status: "metadata_only",
        coverage_level: "METADATA_ONLY",
        last_error: null,
        next_available_action: "Run approved collector",
      },
    ]),
  getPracticeSummary: () =>
    Promise.resolve({
      external_references: 2534,
      hosted_records: 50,
      awaiting_review: 20,
      published_hosted_questions: 30,
      approved_sources: 5,
      last_successful_collection: "2026-07-21T16:00:00Z",
      source_counts: [],
    }),
  getContentImports: () => Promise.resolve([{ rejected_count: 2 }]),
  getReviewQueue: () => Promise.resolve(Array.from({ length: 20 }, () => ({}))),
  getPublishedQuestions: () =>
    Promise.resolve({
      items: [
        {
          external_id: "PY-0005",
          title: "Worker batch",
          slug: "worker-batch",
          track: "python-engineering",
          difficulty: "advanced",
          role_level: "senior",
          estimated_duration_minutes: 35,
          publication_version: "1.0.0",
          learning_objectives: [],
          skills: [],
          company_style_tags: [],
        },
      ],
      page: 1,
      page_size: 100,
      total: 30,
      has_next: false,
    }),
  runApprovedCollectors: vi.fn(),
}));

describe("CatalogStatus", () => {
  it("renders database-backed launch totals and breakdowns", async () => {
    render(
      <QueryProvider>
        <CatalogStatus />
      </QueryProvider>,
    );

    expect(await screen.findByText("Hosted packages")).toBeInTheDocument();
    expect(screen.getByText("Published hosted")).toBeInTheDocument();
    expect(screen.getByText("External references")).toBeInTheDocument();
    expect(screen.getByText("Review backlog")).toBeInTheDocument();
    expect(screen.getByText("Import failures")).toBeInTheDocument();
    expect(screen.getByText("Published content by track")).toBeInTheDocument();
    expect(
      screen.getByText("Published content by difficulty"),
    ).toBeInTheDocument();
    expect(screen.getByText("python engineering")).toBeInTheDocument();
  });
});
