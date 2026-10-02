import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { StudyWorkspace } from "./study-workspace";

vi.mock("@/lib/auth", () => ({
  useAuth: () => ({ principal: { subject_id: "candidate-account-1" } }),
}));

describe("StudyWorkspace", () => {
  afterEach(() => cleanup());

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
    fireEvent.submit(screen.getByLabelText("Project title").closest("form")!);

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

  it("keeps study data in the signed-in account scope and deletes its project records", async () => {
    render(<StudyWorkspace />);
    const title = (await screen.findAllByLabelText("Project title"))[0]!;
    fireEvent.change(title, { target: { value: "Private study" } });
    fireEvent.submit(title.closest("form")!);
    expect((await screen.findAllByText("Private study")).length).toBeGreaterThan(0);
    expect(window.localStorage.getItem("skillforge.study-workspace.v1.candidate-account-1")).toContain("Private study");
    fireEvent.click(screen.getByRole("button", { name: /delete project/i }));
    expect(screen.queryAllByText("Private study")).toHaveLength(0);
  });

  it("caps new task durations to the range accepted by browser-storage parsing", async () => {
    render(<StudyWorkspace />);
    await screen.findByText("Plan the work, practice the skill, keep the evidence.");
    const projectTitle = (await screen.findAllByLabelText("Project title"))[0]!;
    fireEvent.change(projectTitle, { target: { value: "Bounded plan" } });
    fireEvent.submit(projectTitle.closest("form")!);

    fireEvent.change(screen.getByLabelText("Task title"), {
      target: { value: "Long study block" },
    });
    fireEvent.change(screen.getByLabelText("Task minutes"), {
      target: { value: "1500" },
    });
    fireEvent.submit(screen.getByLabelText("Task title").closest("form")!);
    expect(await screen.findAllByText("Long study block")).toHaveLength(2);

    const stored = await waitFor(() => {
      const value = window.localStorage.getItem(
        "skillforge.study-workspace.v1.candidate-account-1",
      );
      const parsed = value ? JSON.parse(value) : null;
      expect(parsed?.projects[0]?.tasks[0]?.estimatedMinutes).toBeDefined();
      return parsed;
    });
    expect(stored.projects[0].tasks[0].estimatedMinutes).toBe(1440);
    expect(screen.getByLabelText("Task minutes")).toHaveAttribute("max", "1440");
  });
});
