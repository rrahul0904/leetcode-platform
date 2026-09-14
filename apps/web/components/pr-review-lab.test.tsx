import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { PrReviewLab } from "./pr-review-lab";

afterEach(() => cleanup());

describe("PrReviewLab", () => {
  it("supports inline review comments and deterministic grading", () => {
    render(<PrReviewLab />);

    expect(screen.getByRole("heading", { name: "PR Review Lab" })).toBeInTheDocument();

    fireEvent.click(
      screen.getByRole("button", {
        name: "Review apps/api/src/payments/capture.ts line 12",
      }),
    );
    fireEvent.change(screen.getByRole("textbox", { name: "Review comment" }), {
      target: {
        value:
          "The timestamp changes the idempotency key on every retry, so a retried capture can charge the customer twice.",
      },
    });
    fireEvent.change(screen.getByLabelText("Severity"), {
      target: { value: "blocker" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Add comment" }));
    fireEvent.click(screen.getByRole("button", { name: "Submit review" }));

    expect(screen.getByText("Review scored")).toBeInTheDocument();
    expect(screen.getByText(/1 of 3 findings caught/)).toBeInTheDocument();
    expect(screen.getByText("Retry idempotency is broken")).toBeInTheDocument();
  });
});
