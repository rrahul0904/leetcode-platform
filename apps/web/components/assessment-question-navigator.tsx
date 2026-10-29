"use client";

import type { AssessmentProgress } from "@/lib/assessment-workspace";

type Props = {
  progress: AssessmentProgress;
  selected: number;
  onSelect: (questionNumber: number) => void;
};

const labels = {
  code: "Coding",
  written: "Written",
  multiple_choice: "Multiple choice",
} as const;

export function AssessmentQuestionNavigator({ progress, selected, onSelect }: Props) {
  return (
    <nav aria-label="Assessment question navigator"
      className="h-fit overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm lg:sticky lg:top-6">
      <div className="border-b border-slate-100 p-5">
        <p className="text-xs font-bold uppercase tracking-[0.16em] text-sky-700">Your progress</p>
        <p className="mt-2 text-2xl font-bold text-slate-900">
          {progress.answered}<span className="text-base font-normal text-slate-500"> / {progress.total} answered</span>
        </p>
        <div className="mt-3 h-2 overflow-hidden rounded-full bg-slate-100"
          role="progressbar" aria-label="Questions answered"
          aria-valuemin={0} aria-valuemax={100} aria-valuenow={progress.percentage}>
          <div className="h-full rounded-full bg-sky-600 transition-all"
            style={{ width: progress.percentage + "%" }} />
        </div>
        <div className="mt-3 flex flex-wrap gap-3 text-xs text-slate-600">
          <span><span className="mr-1 text-emerald-600">●</span>{progress.saved} saved</span>
          <span><span className="mr-1 text-amber-600">●</span>{progress.unsaved} unsaved</span>
          <span><span className="mr-1 text-slate-400">●</span>{progress.unanswered} unanswered</span>
        </div>
      </div>
      <ol className="space-y-1 p-3">
        {progress.questions.map((question) => (
          <li key={question.number}>
            <button type="button"
              onClick={() => onSelect(question.number)}
              aria-current={selected === question.number ? "step" : undefined}
              aria-label={"Question " + question.number + ", " + labels[question.kind] + ", " + question.state}
              className={
                "flex w-full items-center gap-3 rounded-xl border p-3 text-left transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sky-500 " +
                (selected === question.number
                  ? "border-sky-500 bg-sky-50 text-sky-900"
                  : "border-transparent text-slate-700 hover:border-slate-200 hover:bg-slate-50")
              }>
              <span className={
                "flex h-9 w-9 shrink-0 items-center justify-center rounded-lg text-sm font-bold " +
                (selected === question.number ? "bg-sky-600 text-white" : "bg-slate-100 text-slate-800")
              }>{String(question.number).padStart(2, "0")}</span>
              <span className="min-w-0 flex-1">
                <span className="block text-sm font-semibold">{labels[question.kind]}</span>
                <span className="block text-xs text-slate-500">{question.marks} points</span>
              </span>
              <span className={
                "text-xs font-semibold " +
                (question.state === "saved" ? "text-emerald-700"
                  : question.state === "unsaved" ? "text-amber-700" : "text-slate-400")
              }>{question.state === "saved" ? "Saved" : question.state === "unsaved" ? "Edited" : "—"}</span>
            </button>
          </li>
        ))}
      </ol>
      <div className="border-t border-slate-100 p-4 text-xs leading-5 text-slate-500">
        Responses are saved to the server. Unsaved changes must finish saving before submission.
      </div>
    </nav>
  );
}
