import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { QueryProvider } from "./query-provider";
import { QuestionBank } from "./question-bank";

const { replaceMock, getBookmarkedQuestionsMock } = vi.hoisted(() => ({
  replaceMock: vi.fn(),
  getBookmarkedQuestionsMock: vi.fn(),
}));
let currentSearchParams = new URLSearchParams();

vi.mock("next/navigation", () => ({
  usePathname: () => "/question-bank",
  useRouter: () => ({ replace: replaceMock }),
  useSearchParams: () => currentSearchParams,
}));

const hostedPage = {
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
      learning_objectives: ["Translate a production scenario into invariants."],
      skills: ["reliability", "algorithms"],
      company_style_tags: ["independent-production-interview"],
    },
  ],
  page: 1,
  page_size: 12,
  total: 1,
  has_next: false,
};

vi.mock("@/lib/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api")>()),
  getPublishedQuestions: () => Promise.resolve(hostedPage),
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

vi.mock("@/lib/question-engagement-client", () => ({
  getBookmarkedQuestions: getBookmarkedQuestionsMock,
}));

beforeEach(() => {
  currentSearchParams = new URLSearchParams();
  replaceMock.mockReset();
  getBookmarkedQuestionsMock.mockReset();
  getBookmarkedQuestionsMock.mockResolvedValue(hostedPage);
});

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
    expect(screen.getByText("Hosted prompt · Workspace ready")).toBeInTheDocument();
    expect(screen.getByText("Senior")).toBeInTheDocument();
  });

  it("uses the candidate bookmark catalog when bookmarked=true", async () => {
    currentSearchParams = new URLSearchParams("bookmarked=true&track=python-engineering");
    render(
      <QueryProvider>
        <QuestionBank />
      </QueryProvider>,
    );

    expect(
      await screen.findByText("Select a Bounded Priority Worker Batch"),
    ).toBeInTheDocument();
    expect(getBookmarkedQuestionsMock).toHaveBeenCalled();
    expect(screen.getByRole("checkbox", { name: /bookmarked only/i })).toBeChecked();
    expect(screen.queryByText("External practice", { selector: "h2" })).not.toBeInTheDocument();
  });

  it("writes filter changes back to the question-bank URL", async () => {
    render(
      <QueryProvider>
        <QuestionBank />
      </QueryProvider>,
    );
    await screen.findByText("Select a Bounded Priority Worker Batch");

    fireEvent.click(screen.getByRole("checkbox", { name: /bookmarked only/i }));
    expect(replaceMock).toHaveBeenCalledWith(
      "/question-bank?bookmarked=true",
      { scroll: false },
    );
  });
});
