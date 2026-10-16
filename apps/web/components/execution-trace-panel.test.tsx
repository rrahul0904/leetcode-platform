import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { ExecutionTrace } from "@/lib/execution-trace";

import { ExecutionTracePanel } from "./execution-trace-panel";

const trace: ExecutionTrace = {
  version: 1,
  runtime: "python3.13",
  limits: {
    maxEvents: 20,
    maxFrames: 10,
    maxBindingsPerEvent: 10,
    maxTextLength: 1_000,
  },
  outcome: { status: "completed" },
  truncated: false,
  events: [
    {
      seq: 1,
      kind: "call",
      location: { line: 1 },
      bindings: [{ name: "n", value: { kind: "primitive", value: 2 } }],
      stack: [{ id: "solve", name: "solve", location: { line: 1 } }],
    },
    {
      seq: 2,
      kind: "assign",
      location: { line: 2 },
      bindings: [{ name: "answer", value: { kind: "primitive", value: 4 } }],
      summary: "answer changed",
    },
  ],
};

describe("ExecutionTracePanel", () => {
  it("moves through immutable replay state", () => {
    render(<ExecutionTracePanel trace={trace} />);

    expect(screen.getByText("call")).toBeInTheDocument();
    expect(screen.getByText("n")).toBeInTheDocument();
    expect(screen.queryByText("answer")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Next trace step" }));

    expect(screen.getByText("assign")).toBeInTheDocument();
    expect(screen.getByText("answer")).toBeInTheDocument();
    expect(screen.getByText("answer changed")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Previous trace step" }));

    expect(screen.getByText("call")).toBeInTheDocument();
    expect(screen.queryByText("answer")).not.toBeInTheDocument();
  });
});
