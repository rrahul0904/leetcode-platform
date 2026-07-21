import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ExternalPractice } from "./external-practice";
import { QueryProvider } from "./query-provider";

vi.mock("@/lib/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api")>()),
  getExternalReferenceFacets: () =>
    Promise.resolve({
      sources: [{ value: "source-1", label: "Exercism", count: 1127 }],
      difficulties: [
        { value: "intermediate", label: "Intermediate", count: 1 },
      ],
      competencies: [{ value: "algorithms", label: "Algorithms", count: 1 }],
    }),
  getExternalReferences: () =>
    Promise.resolve({
      items: [
        {
          reference_id: "reference-1",
          source_id: "source-1",
          source_name: "Exercism",
          canonical_domain: "exercism.org",
          coverage_level: "METADATA_ONLY",
          canonical_url: "https://exercism.org/tracks/python/exercises/two-fer",
          title: "Two Fer",
          abstract: null,
          difficulty: "intermediate",
          topic_metadata: ["python"],
          patterns: ["string-processing"],
          competency_slugs: ["algorithms"],
          source_availability: "available",
          access_tier: "public",
          technology_freshness: "stable",
          first_seen_at: "2026-07-21T00:00:00Z",
          last_seen_at: "2026-07-21T00:00:00Z",
          last_verified_at: null,
          review_due_at: null,
        },
      ],
      page: 1,
      page_size: 12,
      total: 2534,
      has_next: true,
    }),
}));

describe("ExternalPractice", () => {
  it("renders PostgreSQL reference metadata with a safe canonical link", async () => {
    render(
      <QueryProvider>
        <ExternalPractice />
      </QueryProvider>,
    );
    expect(await screen.findByText("Two Fer")).toBeInTheDocument();
    expect(
      screen.getByText("2,534 external practice references"),
    ).toBeInTheDocument();
    const link = screen.getByRole("link", { name: /open on source/i });
    expect(link).toHaveAttribute(
      "href",
      "https://exercism.org/tracks/python/exercises/two-fer",
    );
    expect(link).toHaveAttribute("target", "_blank");
    expect(link).toHaveAttribute("rel", "noopener noreferrer");
  });
});
