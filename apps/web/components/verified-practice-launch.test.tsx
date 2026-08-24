import { describe, expect, it } from "vitest";

import { practiceHrefForProblem } from "@/components/verified-practice-launch";
import type { ProblemDetail } from "@/lib/knowledge-api";

function problem(overrides: Partial<ProblemDetail> = {}): ProblemDetail {
  return {
    id: "problem-1",
    canonical_key: "large:1m:Q-1",
    external_id: "Q-1",
    title: "Question",
    slug: "question",
    summary: null,
    difficulty: "hard",
    source_url: null,
    publication_status: "published",
    review_status: "approved",
    availability: "runnable",
    acceptance_rate: null,
    popularity: null,
    languages: ["python"],
    topics: ["python"],
    companies: [],
    platform: "Python",
    subtopic: "algorithms",
    seniority: "Senior",
    industry: "SaaS",
    canonical_classification: "canonical_candidate",
    practice_question_slug: "published-python-question",
    practice_runtime: "python",
    description: "Solve it.",
    input_format: null,
    output_format: null,
    examples: [],
    constraints: [],
    hints: [],
    editorial_available: false,
    solution_count: 0,
    ...overrides,
  };
}

describe("verified practice bridge", () => {
  it("opens only the authored question slug from a verified runnable link", () => {
    expect(practiceHrefForProblem(problem())).toBe(
      "/practice/published-python-question",
    );
  });

  it("does not create a practice route for reference-only material", () => {
    expect(
      practiceHrefForProblem(
        problem({
          availability: "reference_only",
          practice_question_slug: null,
          practice_runtime: null,
        }),
      ),
    ).toBeNull();
  });

  it("fails closed if a runnable label is missing the verified practice target", () => {
    expect(
      practiceHrefForProblem(
        problem({ practice_question_slug: null, practice_runtime: null }),
      ),
    ).toBeNull();
  });
});
