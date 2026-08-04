import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ControlledCodeEditor } from "@/components/controlled-code-editor";

describe("ControlledCodeEditor", () => {
  it("renders PostgreSQL mode with a controlled draft", () => {
    render(
      <ControlledCodeEditor
        language="sql"
        source="SELECT 1;"
        starterSource="SELECT 1;"
        saveState="Saved"
        onChange={vi.fn()}
        onRun={vi.fn()}
        onSubmit={vi.fn()}
      />,
    );

    expect(screen.getByText("POSTGRESQL 18")).toBeInTheDocument();
    expect(screen.getByLabelText("POSTGRESQL 18 source code")).toHaveValue(
      "SELECT 1;",
    );
  });

  it("maps Run and Submit keyboard shortcuts to durable actions", () => {
    const onRun = vi.fn();
    const onSubmit = vi.fn();
    render(
      <ControlledCodeEditor
        language="python"
        source="print('ready')"
        starterSource=""
        saveState="Saved"
        onChange={vi.fn()}
        onRun={onRun}
        onSubmit={onSubmit}
      />,
    );

    const editor = screen.getByLabelText("PYTHON 3.13 source code");
    fireEvent.keyDown(editor, { key: "Enter", ctrlKey: true });
    fireEvent.keyDown(editor, { key: "Enter", ctrlKey: true, shiftKey: true });

    expect(onRun).toHaveBeenCalledTimes(1);
    expect(onSubmit).toHaveBeenCalledTimes(1);
  });

  it("inserts four spaces for Tab through the controlled change callback", () => {
    const onChange = vi.fn();
    render(
      <ControlledCodeEditor
        language="python"
        source=""
        starterSource=""
        saveState="Saved"
        onChange={onChange}
        onRun={vi.fn()}
        onSubmit={vi.fn()}
      />,
    );

    fireEvent.keyDown(screen.getByLabelText("PYTHON 3.13 source code"), {
      key: "Tab",
    });
    expect(onChange).toHaveBeenCalledWith("    ");
  });
});
