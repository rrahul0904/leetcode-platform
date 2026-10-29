import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { AssessmentExecutionReceipt } from "./assessment-execution-receipt";
import type { CandidateCodeExecution } from "@/lib/employer-assessment-api";

const completed: CandidateCodeExecution = {
  id: "receipt-123",
  attempt_id: "attempt-456",
  question_number: 2,
  language: "sql",
  execution_mode: "SUBMIT",
  status: "completed",
  created_at: "2026-10-28T22:00:00Z",
  runtime_ms: 15,
  public_results: [{
    test_id: "sample_one", name: "Visible sample",
    passed: true, expected: null, actual: null, error_category: null,
  }],
  hidden_total: 4,
  hidden_passed: 3,
  awarded_marks: 75,
  error_category: null,
  duplicate: false,
};

describe("candidate execution receipt", () => {
  it("shows only aggregate hidden marks, not confidential fixture values", () => {
    const { container } = render(
      <AssessmentExecutionReceipt mode="SUBMIT" receipt={completed} />,
    );
    expect(screen.getByText("Final grading receipt")).toBeTruthy();
    expect(screen.getByText("3 / 4 passed")).toBeTruthy();
    expect(screen.getByText("75")).toBeTruthy();
    expect(container.textContent).not.toContain("hidden_one");
    expect(container.textContent).not.toContain("expected_output");
  });

  it("does not misrepresent queued executions as completed", () => {
    render(
      <AssessmentExecutionReceipt mode="RUN"
        receipt={{ ...completed, status: "queued", execution_mode: "RUN",
          runtime_ms: null, public_results: null,
          hidden_total: null, hidden_passed: null, awarded_marks: null }} />,
    );
    expect(screen.getByText("Waiting for isolated runner")).toBeTruthy();
    expect(screen.getByText(/results update automatically/i)).toBeTruthy();
  });

  it("never renders final hidden grading as part of the sample Run tab", () => {
    const { container } = render(
      <AssessmentExecutionReceipt mode="RUN" receipt={{ ...completed, execution_mode: "RUN" }} />,
    );
    expect(container.textContent).not.toContain("Private test summary");
    expect(container.textContent).not.toContain("3 / 4 passed");
  });
});
