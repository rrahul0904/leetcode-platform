import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { LearningPaths } from "./learning-paths";

describe("LearningPaths", () => {
  it("renders the Data Engineering path and routes into canonical practice", () => {
    render(<LearningPaths />);

    expect(screen.getByText("Data engineering interviews")).toBeInTheDocument();
    const practice = screen.getAllByRole("link", { name: /start focused practice/i })[0];
    expect(practice).toHaveAttribute(
      "href",
      "/question-bank?track=data-engineering",
    );
    expect(
      screen.getAllByRole("link", { name: /run a mock interview/i })[0],
    ).toHaveAttribute("href", "/mock-interviews");
  });
});
