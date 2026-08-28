import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { QueryProvider } from "./query-provider";
import { QuestionBank } from "./question-bank";

const { replaceMock, getCandidateQuestionsMock } = vi.hoisted(() => ({
  replaceMock: vi.fn(),
  getCandidateQuestionsMock: vi.fn(),
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
  getCandidateQuestions: getCandidateQuestionsMock,
}));

beforeEach(() => {
  currentSearchParams = new URLSearchParams();
  replaceMock.mockReset();
  getCandidateQuestionsMock.mockReset();
  getCandidateQuestionsMock.mockResolvedValue(hostedPage);
});

afterEach(() => {
  cleanup();
});

describe("QuestionBank", () => {
  it("renders unified practice navigation and candidate-safe hosted metadata", async () => {
    render(
      <QueryProvider>
        <QuestionBank />
      </QueryProvider>,
    );

    const card = await screen.findByRole("link", {
      name: /Select a Bounded Priority Worker Batch/i,
    });
    expect(card).toHaveAttribute(
      "href",
      "/questions/py-0005-select-a-bounded-priority-worker-batch",
    );
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
    expect(screen.getByText("Check question details")).toBeInTheDocument();
    expect(screen.queryByText(/Workspace ready/i)).not.toBeInTheDocument();
    expect(screen.getByText("Senior")).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "Attempted" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "Passed" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "Python coding" })).toBeInTheDocument();
  });

  it("uses candidate context when bookmarked=true", async () => {
    currentSearchParams = new URLSearchParams("bookmarked=true&track=python-engineering");
    render(
      <QueryProvider>
        <QuestionBank />
      </QueryProvider>,
    );

    expect(
      await screen.findByText("Select a Bounded Priority Worker Batch"),
    ).toBeInTheDocument();
    expect(getCandidateQuestionsMock).toHaveBeenCalledWith(
      expect.objectContaining({ track: "python-engineering" }),
      expect.anything(),
      true,
    );
    expect(screen.getByRole("checkbox", { name: /bookmarked only/i })).toBeChecked();
    expect(screen.queryByText("External practice", { selector: "h2" })).not.toBeInTheDocument();
  });

  it("passes persisted completion state to the candidate catalog", async () => {
    currentSearchParams = new URLSearchParams("completion=passed");
    render(
      <QueryProvider>
        <QuestionBank />
      </QueryProvider>,
    );
    await screen.findByText("Select a Bounded Priority Worker Batch");

    expect(getCandidateQuestionsMock).toHaveBeenCalledWith(
      expect.objectContaining({ completionStatus: "passed" }),
      expect.anything(),
      undefined,
    );
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
