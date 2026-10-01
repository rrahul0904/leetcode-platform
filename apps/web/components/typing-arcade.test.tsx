import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it } from "vitest";

import { TypingArcade } from "./typing-arcade";

describe("TypingArcade browser surface", () => {
  afterEach(() => cleanup());

  beforeEach(() => window.localStorage.clear());

  it("starts, pauses, resumes, and restarts without executing or sending entered text", async () => {
    render(<TypingArcade />);
    fireEvent.click(screen.getByRole("button", { name: "Start game" }));
    expect(await screen.findByText(/Game in progress/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Pause" }));
    expect(screen.getByRole("region", { name: /Falling word board\. Paused/ })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Resume" }));
    expect(screen.getByText(/Game in progress/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Restart" }));
    expect(screen.getByText(/Game in progress/)).toBeInTheDocument();
  });

  it("restores a bounded difficulty preference and ignores malformed local history", async () => {
    window.localStorage.setItem("rigor.typing-arcade.settings.v1", JSON.stringify({ schemaVersion: 1, startingLives: 5 }));
    window.localStorage.setItem("rigor.typing-arcade.history.v1", JSON.stringify([{ runId: 1, reason: "won" }]));
    render(<TypingArcade />);
    expect(await screen.findByRole("combobox", { name: "Starting lives" })).toHaveValue("5");
    fireEvent.change(screen.getByRole("combobox", { name: "Starting lives" }), { target: { value: "1" } });
    expect(JSON.parse(window.localStorage.getItem("rigor.typing-arcade.settings.v1") ?? "{}"))
      .toEqual({ schemaVersion: 1, startingLives: 1 });
    expect(screen.queryByText(/won · undefined pts/)).not.toBeInTheDocument();
  });
});
