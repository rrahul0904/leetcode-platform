import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { GuidedPracticeJourney } from "./guided-practice-journey";

const baseProps = {
  slug: "reliable-event-aggregation",
  learningObjectives: ["Choose a reliable aggregation strategy."],
  constraints: ["Handle duplicate events safely."],
};

afterEach(() => {
  cleanup();
  window.localStorage.clear();
  vi.clearAllMocks();
});

describe("GuidedPracticeJourney", () => {
  it("offers a non-scoring guided nudge", async () => {
    render(<GuidedPracticeJourney {...baseProps} />);

    fireEvent.click(screen.getByRole("button", { name: "Show guided nudge" }));

    expect(await screen.findByText("Guided nudge")).toBeInTheDocument();
    expect(screen.getByText("Using support never changes your score.")).toBeInTheDocument();
  });

  it("lets the candidate hide the timer without changing practice state", async () => {
    const onFocusModeChange = vi.fn();
    render(
      <GuidedPracticeJourney
        {...baseProps}
        onFocusModeChange={onFocusModeChange}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Hide timer" }));

    await waitFor(() => expect(onFocusModeChange).toHaveBeenLastCalledWith(true));
    expect(screen.getByRole("button", { name: "Show timer" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
  });

  it("requires a short self-explanation before signing off the Practice stage", () => {
    render(<GuidedPracticeJourney {...baseProps} />);

    fireEvent.click(screen.getByRole("tab", { name: /3\. Practice/i }));
    const complete = screen.getByRole("button", { name: "Mark this step complete" });
    expect(complete).toBeDisabled();

    fireEvent.change(
      screen.getByLabelText("Explain your planned approach and complexity in your own words."),
      {
        target: {
          value:
            "I preserve one aggregation invariant and process each event once, so time is linear.",
        },
      },
    );

    expect(complete).not.toBeDisabled();
  });

  it("restores candidate-owned stage progress from the browser", async () => {
    const first = render(<GuidedPracticeJourney {...baseProps} />);

    fireEvent.click(screen.getByRole("button", { name: "Mark this step complete" }));
    await waitFor(() =>
      expect(screen.getByText("1 of 5 stages signed off")).toBeInTheDocument(),
    );
    await waitFor(() =>
      expect(window.localStorage.getItem("skillsforge.guided-practice:reliable-event-aggregation"))
        .toContain('"study"'),
    );
    first.unmount();

    render(<GuidedPracticeJourney {...baseProps} />);

    expect(await screen.findByText("1 of 5 stages signed off")).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: /2\. Discover/i })).toHaveAttribute(
      "aria-selected",
      "true",
    );
  });
});
