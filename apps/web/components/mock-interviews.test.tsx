import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { MockInterviews } from "./mock-interviews";

describe("recording-grade mock exam", () => {
  it("supports the complete intro, navigation, answer, flag, and submission flow", () => {
    render(<MockInterviews />);

    expect(screen.getByRole("heading", { name: "Mock Exam" })).toBeInTheDocument();
    expect(screen.getByText("12", { selector: "strong" })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /start mock exam/i }));

    expect(screen.getByLabelText("Question navigator")).toBeInTheDocument();
    expect(screen.getByText("QUESTION 1 OF 12")).toBeInTheDocument();
    expect(screen.getByText("45:00")).toBeInTheDocument();

    fireEvent.click(
      screen.getByLabelText(
        /Inspect retained task references, queue ownership, and cleanup paths before scaling/,
      ),
    );
    expect(screen.getByLabelText("Question 1, answered")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Flag" }));
    expect(screen.getByRole("button", { name: "Flagged" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );

    fireEvent.click(screen.getByRole("button", { name: /^next/i }));
    expect(screen.getByText("QUESTION 2 OF 12")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /submit exam/i }));
    expect(screen.getByRole("heading", { name: "Decisions captured." })).toBeInTheDocument();
    expect(screen.getByText(/You answered 1 of 12 questions/)).toBeInTheDocument();
    expect(screen.getByText(/flagged 1 item/)).toBeInTheDocument();
  });
});
