import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { DesignInterviewTimer } from "./design-interview-timer";

beforeEach(() => {
  vi.useFakeTimers();
  vi.setSystemTime(new Date("2026-09-14T16:00:00Z"));
});

afterEach(() => {
  cleanup();
  window.localStorage.clear();
  vi.useRealTimers();
});

describe("DesignInterviewTimer", () => {
  it("starts, advances, pauses, and resumes the interview clock", () => {
    render(<DesignInterviewTimer />);

    expect(screen.getByText("45:00")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Start" }));

    vi.advanceTimersByTime(5_000);
    expect(screen.getByText("44:55")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Pause" }));
    vi.advanceTimersByTime(5_000);
    expect(screen.getByText("44:55")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Resume" }));
    vi.advanceTimersByTime(1_000);
    expect(screen.getByText("44:54")).toBeInTheDocument();
  });

  it("changes duration presets and persists the selected timer", () => {
    render(<DesignInterviewTimer />);

    fireEvent.click(screen.getByRole("button", { name: "30 min" }));
    expect(screen.getByText("30:00")).toBeInTheDocument();

    const stored = window.localStorage.getItem("skillforge-design-interview-timer-v1");
    expect(stored).not.toBeNull();
    expect(JSON.parse(stored ?? "{}")).toEqual(
      expect.objectContaining({
        durationSeconds: 1800,
        elapsedSeconds: 0,
        running: false,
      }),
    );
  });
});
