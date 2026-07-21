import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ContentReview } from "./content-review";
import { MockInterviews } from "./mock-interviews";
import { QualityGates } from "./quality-gates";
import { QueryProvider } from "./query-provider";
import { Reviewers } from "./reviewers";

vi.mock("@/lib/auth", () => ({
  useAuth: () => ({
    principal: {
      display_name: "Terry Technical",
      roles: ["technical-reviewer"],
      permissions: ["review:read", "review:technical"],
    },
  }),
}));

vi.mock("@/lib/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api")>()),
  getReviewQueue: () => Promise.resolve([]),
}));

describe("product surfaces", () => {
  it("starts and resets a deterministic mock session", () => {
    render(<MockInterviews />);
    fireEvent.click(
      screen.getByRole("button", { name: /start local session/i }),
    );
    expect(
      screen.getByRole("button", { name: /reset session/i }),
    ).toBeInTheDocument();
  });

  it("filters the quality gate board", () => {
    render(<QualityGates />);
    fireEvent.change(screen.getByLabelText("Filter gates"), {
      target: { value: "attention" },
    });
    expect(screen.getByText("Reference integrity")).toBeInTheDocument();
    expect(screen.queryByText("Executable tests")).not.toBeInTheDocument();
  });

  it("enforces independent reviewer assignment", () => {
    render(<Reviewers />);
    const name = screen.getByLabelText("Display name");
    fireEvent.change(name, { target: { value: "Alex Reviewer" } });
    fireEvent.click(
      screen.getByRole("button", { name: /add to local roster/i }),
    );
    fireEvent.change(screen.getByLabelText("Technical reviewer"), {
      target: { value: "1" },
    });
    fireEvent.change(screen.getByLabelText("Editorial reviewer"), {
      target: { value: "1" },
    });
    expect(screen.getByText(/independence violation/i)).toBeInTheDocument();
  });

  it("renders the identity-backed durable review queue", async () => {
    render(
      <QueryProvider>
        <ContentReview />
      </QueryProvider>,
    );
    expect(
      await screen.findByText("The review queue is empty."),
    ).toBeInTheDocument();
    expect(screen.getByText("Terry Technical")).toBeInTheDocument();
  });
});
