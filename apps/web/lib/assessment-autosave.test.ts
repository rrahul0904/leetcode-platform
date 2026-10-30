import { describe, expect, it } from "vitest";
import { nextPendingAssessmentResponse } from "./assessment-autosave";

describe("candidate assessment autosave queue", () => {
  it("persists modified source from a non-visible question first", () => {
    const draft = nextPendingAssessmentResponse(
      "attempt-one", [1, 2],
      { "1": "", "2": "" },
      { "1": "SELECT 1", "2": "def solve(): return 1" },
      null,
    );
    expect(draft).toMatchObject({ number: 1, source: "SELECT 1" });
    const next = nextPendingAssessmentResponse(
      "attempt-one", [1, 2],
      { "1": "SELECT 1", "2": "" },
      { "1": "SELECT 1", "2": "def solve(): return 1" },
      draft?.revision ?? null,
    );
    expect(next).toMatchObject({ number: 2, source: "def solve(): return 1" });
  });

  it("does not replay the same rejected save endlessly but accepts edits", () => {
    const first = nextPendingAssessmentResponse(
      "attempt", [1], {}, { "1": "SELECT abc" }, null,
    );
    expect(first).not.toBeNull();
    expect(nextPendingAssessmentResponse(
      "attempt", [1], {}, { "1": "SELECT abc" }, first?.revision ?? null,
    )).toBeNull();
    expect(nextPendingAssessmentResponse(
      "attempt", [1], {}, { "1": "SELECT abcd" }, first?.revision ?? null,
    )?.source).toBe("SELECT abcd");
  });

  it("never queues empty, unchanged, or unassigned question responses", () => {
    expect(nextPendingAssessmentResponse(
      "attempt", [1, 2], { "1": "SELECT 1" },
      { "1": "SELECT 1", "2": "", "99": "DO NOT SAVE" }, null,
    )).toBeNull();
  });

  it("autosaves a deliberately cleared server-owned answer", () => {
    const pending = nextPendingAssessmentResponse(
      "attempt", [1], { "1": "SELECT secret_value" }, { "1": "" }, null,
    );
    expect(pending).toMatchObject({ number: 1, source: "" });
    expect(nextPendingAssessmentResponse(
      "attempt", [1], { "1": "" }, { "1": "" }, pending?.revision ?? null,
    )).toBeNull();
  });

  it("fences revisions by candidate attempt id", () => {
    const first = nextPendingAssessmentResponse(
      "first", [1], {}, { "1": "SELECT 1" }, null,
    );
    expect(nextPendingAssessmentResponse(
      "second", [1], {}, { "1": "SELECT 1" }, first?.revision ?? null,
    )?.number).toBe(1);
  });
});
