import type { AssessmentQuestion } from "@/lib/employer-assessment-api";

export type AssessmentQuestionProgress = {
  number: number;
  kind: AssessmentQuestion["kind"];
  marks: number;
  state: "unanswered" | "unsaved" | "saved";
};

export type AssessmentProgress = {
  total: number;
  answered: number;
  saved: number;
  unsaved: number;
  unanswered: number;
  percentage: number;
  questions: AssessmentQuestionProgress[];
};

/** Pure, UI-safe progress calculation. The server, not this helper, decides submission validity. */
export function assessmentProgress(
  questions: AssessmentQuestion[],
  savedAnswers: Record<string, string>,
  drafts: Record<string, string>,
): AssessmentProgress {
  const statuses = questions.map((question) => {
    const key = String(question.number);
    const saved = savedAnswers[key] ?? "";
    const draft = drafts[key] ?? saved;
    const state: AssessmentQuestionProgress["state"] =
      draft !== saved ? "unsaved" : draft.trim() ? "saved" : "unanswered";
    return {
      number: question.number,
      kind: question.kind,
      marks: question.marks,
      state,
    };
  });
  const answered = statuses.filter((question) => question.state !== "unanswered").length;
  const saved = statuses.filter((question) => question.state === "saved").length;
  const unsaved = statuses.filter((question) => question.state === "unsaved").length;
  return {
    total: statuses.length,
    answered,
    saved,
    unsaved,
    unanswered: statuses.length - answered,
    percentage: statuses.length ? Math.round(answered / statuses.length * 100) : 0,
    questions: statuses,
  };
}

export function assessmentClockTone(secondsLeft: number | null): "normal" | "warning" | "critical" {
  if (secondsLeft === null || secondsLeft > 600) return "normal";
  if (secondsLeft > 120) return "warning";
  return "critical";
}
