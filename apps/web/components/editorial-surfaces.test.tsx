import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { journalArticles } from "@/lib/editorial-content";

import { Journal } from "./journal";
import { JournalArticleView } from "./journal-article";
import { ResourceLibrary } from "./resource-library";

afterEach(cleanup);

describe("editorial candidate surfaces", () => {
  it("renders a featured journal essay and the editorial index", () => {
    render(<Journal />);

    expect(
      screen.getByRole("heading", {
        name: /Ideas for operating under interview pressure/i,
      }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: /Reliability before scale/i }),
    ).toHaveAttribute("href", "/journal/reliability-before-scale");
    expect(screen.getByText("LATEST ESSAYS")).toBeInTheDocument();
    expect(screen.getAllByText(/min read| min$/)).not.toHaveLength(0);
  });

  it("renders long-form sections, outline, and code evidence", () => {
    const article = journalArticles[0];
    expect(article).toBeDefined();
    if (!article) return;

    render(<JournalArticleView article={article} />);

    expect(
      screen.getByRole("heading", {
        level: 1,
        name: "Reliability before scale",
      }),
    ).toBeInTheDocument();
    expect(screen.getByRole("navigation", { name: "Article outline" })).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "Separate acceptance from execution" }),
    ).toBeInTheDocument();
    expect(
      screen.getByLabelText("Separate acceptance from execution code example"),
    ).toHaveTextContent("INSERT INTO execution_outbox");
    expect(screen.getByRole("link", { name: /Practice under time/i })).toHaveAttribute(
      "href",
      "/mock-interviews",
    );
  });

  it("groups practical resources by working category", () => {
    render(<ResourceLibrary />);

    expect(
      screen.getByRole("heading", {
        name: /Practical material for the work between sessions/i,
      }),
    ).toBeInTheDocument();
    expect(screen.getByText("Foundations")).toBeInTheDocument();
    expect(screen.getByText("Practice systems")).toBeInTheDocument();
    expect(screen.getAllByText("Reference").length).toBeGreaterThan(0);
    expect(screen.getByText("Career strategy")).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: /Python execution-contract guide/i }),
    ).toHaveAttribute("href", "/problems?language=python");
    expect(
      screen.getByRole("link", { name: /Staff decision-record workbook/i }),
    ).toHaveAttribute("href", "/learning-paths");
  });
});
