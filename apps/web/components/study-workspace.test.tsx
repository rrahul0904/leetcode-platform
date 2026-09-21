import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";

import { StudyWorkspace } from "./study-workspace";

describe("StudyWorkspace", () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  it("creates a project, task, focus evidence, and review card in one workspace", async () => {
    render(<StudyWorkspace />);

    expect(await screen.findByText("Plan the work, practice the skill, keep the evidence.")).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Project title"), {
      target: { value: "System design" },
    });
    fireEvent.change(screen.getByLabelText("Project goal"), {
      target: { value: "Explain trade-offs clearly" },
    });
    fireEvent.click(screen.getByRole("button", { name: /add project/i }));

    expect(screen.getAllByText("System design").length).toBeGreaterThan(0);

    fireEvent.change(screen.getByLabelText("Task title"), {
      target: { value: "Practice consistency models" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Add task" }));

    expect(screen.getAllByText("Practice consistency models").length).toBeGreaterThan(0);

    fireEvent.click(screen.getByRole("button", { name: /record 25-minute focus block/i }));
    expect(screen.getAllByText("25 min").length).toBeGreaterThan(0);

    fireEvent.change(screen.getByLabelText("Flashcard question"), {
      target: { value: "What is linearizability?" },
    });
    fireEvent.change(screen.getByLabelText("Flashcard answer"), {
      target: { value: "Operations appear to occur atomically in real-time order." },
    });
    fireEvent.click(screen.getByRole("button", { name: /add review card/i }));

    expect(screen.getByText("What is linearizability?")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Reveal answer" }));
    expect(
      screen.getByText("Operations appear to occur atomically in real-time order."),
    ).toBeInTheDocument();
  });
});
