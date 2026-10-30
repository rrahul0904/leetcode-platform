import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { AssessmentCodingPads } from "./assessment-coding-pads";

afterEach(() => cleanup());

const sqlQuestion = {
  number: 3,
  kind: "code" as const,
  language: "sql" as const,
  prompt: "Write a SQL query to count unique IDs in each partition.",
  marks: 100,
  options: [],
};

describe("AssessmentCodingPads", () => {
  it("retains employer-declared SQL runtime, editing and explicit server save", () => {
    const onChange = vi.fn();
    const onSave = vi.fn();
    render(
      <AssessmentCodingPads
        question={sqlQuestion}
        answer="SELECT COUNT(DISTINCT event_id) FROM events"
        active
        working={false}
        dirty
        onChange={onChange}
        onSave={onSave}
      />,
    );
    expect(screen.getByRole("tab", { name: "SQL Pad" })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByRole("tab", { name: "Python Pad" })).toBeDisabled();
    const editor = screen.getByRole("textbox", {
      name: "SQL Pad source response for question 3",
    });
    fireEvent.change(editor, { target: { value: "SELECT 1" } });
    expect(onChange).toHaveBeenCalledWith("SELECT 1");
    fireEvent.click(screen.getByRole("button", { name: "Save source response" }));
    expect(onSave).toHaveBeenCalledTimes(1);
    expect(screen.getByText(/Python and SQL Run requests use the trusted isolated execution service/)).toBeInTheDocument();
  });

  it("reports background autosave without freezing source edits or allowing duplicate submits", () => {
    const onChange = vi.fn();
    const onSave = vi.fn();
    render(
      <AssessmentCodingPads
        question={sqlQuestion}
        answer="SELECT event_id FROM events"
        active
        working={false}
        saving
        dirty
        onChange={onChange}
        onSave={onSave}
      />,
    );
    expect(screen.getByText("Autosaving…")).toBeInTheDocument();
    const editor = screen.getByRole("textbox", {
      name: "SQL Pad source response for question 3",
    });
    expect(editor).toBeEnabled();
    fireEvent.change(editor, { target: { value: "SELECT 42" } });
    expect(onChange).toHaveBeenCalledWith("SELECT 42");
    expect(screen.getByRole("button", { name: "Saving…" })).toBeDisabled();
  });

  it("does not disclose AI code assistance or permit edits after submission", () => {
    const onChange = vi.fn();
    const onSave = vi.fn();
    render(
      <AssessmentCodingPads
        question={{ ...sqlQuestion, language: "python" }}
        answer="def solve(): pass"
        active={false}
        working={false}
        dirty={false}
        onChange={onChange}
        onSave={onSave}
      />,
    );
    expect(screen.getByRole("textbox", {
      name: "Python Pad source response for question 3",
    })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Save source response" })).toBeDisabled();
    fireEvent.click(screen.getByRole("tab", { name: /AI Pad/ }));
    expect(screen.getByText(/AI code hints and answer generation are not enabled/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Open optional AI technical interview/ }))
      .toHaveAttribute("href", "#assessment-ai-interview");
    expect(onChange).not.toHaveBeenCalled();
    expect(onSave).not.toHaveBeenCalled();
  });
});
