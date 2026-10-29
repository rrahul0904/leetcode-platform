import { describe, expect, it } from "vitest";

import { assessmentClockTone, assessmentProgress } from "./assessment-workspace";
import type { AssessmentQuestion } from "./employer-assessment-api";

const questions: AssessmentQuestion[] = [
  { number: 1, kind: "code", language: "python", prompt: "Solve a Python question", marks: 100, options: [] },
  { number: 2, kind: "code", language: "sql", prompt: "Solve a SQL question", marks: 100, options: [] },
  { number: 3, kind: "written", prompt: "Explain the recovery plan", marks: 100, options: [] },
];

describe("assessment workspace progress", () => {
  it("distinguishes server-saved answers from local unsaved edits", () => {
    const result = assessmentProgress(questions,
      { "1": "def solve(): pass", "2": "", "3": "" },
      { "1": "def solve(): pass", "2": "SELECT 1", "3": "" },
    );
    expect(result).toMatchObject({
      total: 3, answered: 2, saved: 1, unsaved: 1, unanswered: 1, percentage: 67,
    });
    expect(result.questions.map((item) => item.state)).toEqual([
      "saved", "unsaved", "unanswered",
    ]);
  });

  it("a deliberately cleared answer is unsaved and unanswered", () => {
    const result = assessmentProgress(questions,
      { "1": "def solve(): pass" },
      { "1": "" },
    );
    expect(result).toMatchObject({
      total: 3, answered: 0, saved: 0, unsaved: 1, unanswered: 3, percentage: 0,
    });
  });

  it("defaults to saved answers while history is restoring", () => {
    const result = assessmentProgress(questions, { "1": "SELECT no_secret" }, {});
    expect(result).toMatchObject({
      total: 3, answered: 1, saved: 1, unsaved: 0, unanswered: 2,
    });
  });

  it("does not divide by zero on legacy empty assessments", () => {
    expect(assessmentProgress([], {}, {})).toMatchObject({
      total: 0, answered: 0, saved: 0, unsaved: 0, unanswered: 0, percentage: 0,
    });
  });

  it("shows warning and critical clock states at intended thresholds", () => {
    expect(assessmentClockTone(null)).toBe("normal");
    expect(assessmentClockTone(601)).toBe("normal");
    expect(assessmentClockTone(600)).toBe("warning");
    expect(assessmentClockTone(121)).toBe("warning");
    expect(assessmentClockTone(120)).toBe("critical");
    expect(assessmentClockTone(-5)).toBe("critical");
  });
});
