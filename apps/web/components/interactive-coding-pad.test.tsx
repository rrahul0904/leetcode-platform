import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { InteractiveCodingPad } from "@/components/interactive-coding-pad";

describe("InteractiveCodingPad", () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  it("renders Python mode with line numbers and custom tests", () => {
    render(
      <InteractiveCodingPad
        questionKey="python-demo"
        language="python"
        initialSource={"def solve():\n    return 1"}
      />,
    );
    expect(screen.getByText("PYTHON 3.13")).toBeInTheDocument();
    expect(screen.getByLabelText("PYTHON 3.13 source code")).toHaveValue(
      "def solve():\n    return 1",
    );
    expect(screen.getByRole("button", { name: "Custom tests" })).toBeInTheDocument();
  });

  it("runs SQL and renders returned rows", async () => {
    const onRun = vi.fn().mockResolvedValue({
      status: "passed",
      message: "Query completed.",
      rows: [{ users: 4 }],
    });
    render(
      <InteractiveCodingPad
        questionKey="sql-demo"
        language="sql"
        initialSource="SELECT 1;"
        executionEnabled
        schema="users(user_id bigint)"
        onRun={onRun}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: "Run" }));
    expect(await screen.findByText("Query completed.")).toBeInTheDocument();
    expect(screen.getByText("users")).toBeInTheDocument();
    expect(screen.getByText("4")).toBeInTheDocument();
  });

  it("inserts spaces for the Tab key", () => {
    render(
      <InteractiveCodingPad
        questionKey="tab-demo"
        language="python"
        initialSource=""
      />,
    );
    const editor = screen.getByLabelText("PYTHON 3.13 source code");
    fireEvent.keyDown(editor, { key: "Tab" });
    expect(editor).toHaveValue("    ");
  });
});
