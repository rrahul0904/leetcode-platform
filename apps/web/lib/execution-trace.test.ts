import { describe, expect, it } from "vitest";

import {
  normalizeExecutionTrace,
  replayExecutionTrace,
  type ExecutionTrace,
} from "./execution-trace";

function fixture(): ExecutionTrace {
  return {
    version: 1,
    runtime: "python3.13",
    limits: {
      maxEvents: 10,
      maxFrames: 3,
      maxBindingsPerEvent: 3,
      maxTextLength: 20,
    },
    outcome: { status: "completed" },
    truncated: false,
    events: [
      {
        seq: 1,
        kind: "call",
        location: { line: 1 },
        bindings: [{ name: "n", value: { kind: "primitive", value: 2 } }],
        stack: [{ id: "f1", name: "solve", location: { line: 1 } }],
      },
      {
        seq: 2,
        kind: "assign",
        location: { line: 2 },
        bindings: [{ name: "answer", value: { kind: "primitive", value: 4 } }],
      },
      {
        seq: 3,
        kind: "output",
        location: { line: 3 },
        stdout: "4\n",
      },
    ],
  };
}

describe("execution trace replay", () => {
  it("reconstructs bindings and output without mutating the trace", () => {
    const trace = fixture();
    const original = structuredClone(trace);
    const state = replayExecutionTrace(trace, 2);

    expect(state.event?.seq).toBe(3);
    expect(state.bindings).toEqual({
      n: { kind: "primitive", value: 2 },
      answer: { kind: "primitive", value: 4 },
    });
    expect(state.stack.map((frame) => frame.name)).toEqual(["solve"]);
    expect(state.stdout).toBe("4\n");
    expect(trace).toEqual(original);
  });

  it("supports replaying backwards from the same immutable artifact", () => {
    const trace = fixture();

    expect(replayExecutionTrace(trace, 1).bindings.answer).toEqual({
      kind: "primitive",
      value: 4,
    });
    expect(replayExecutionTrace(trace, 0).bindings.answer).toBeUndefined();
    expect(replayExecutionTrace(trace, -1).event).toBeNull();
  });

  it("clamps provider artifacts to declared UI budgets", () => {
    const trace = fixture();
    trace.limits.maxEvents = 2;
    trace.limits.maxBindingsPerEvent = 1;
    trace.events[0]!.bindings = [
      { name: "a", value: { kind: "primitive", value: 1 } },
      { name: "b", value: { kind: "primitive", value: 2 } },
    ];

    const normalized = normalizeExecutionTrace(trace);

    expect(normalized.events).toHaveLength(2);
    expect(normalized.events[0]!.bindings).toHaveLength(1);
    expect(normalized.truncated).toBe(true);
  });

  it("rejects non-monotonic sequence numbers instead of replaying misleading state", () => {
    const trace = fixture();
    trace.events[1]!.seq = 1;

    expect(() => normalizeExecutionTrace(trace)).toThrow(
      "Execution trace sequence numbers must be strictly increasing",
    );
  });
});
