"use client";

import { useState } from "react";
import type { AssessmentQuestion } from "@/lib/employer-assessment-api";

type Pad = "python" | "sql" | "ai";

type Props = {
  question: AssessmentQuestion;
  answer: string;
  active: boolean;
  working: boolean;
  saving?: boolean;
  dirty: boolean;
  onChange: (source: string) => void;
  onSave: () => void;
};

/**
 * An authenticated, server-persisted answer editor.
 *
 * Do not run untrusted code in the Next.js process or in the user's browser
 * as a substitute for the isolated, trusted assessment execution controller.
 * AI assistance for hiring is disabled until an approved per-assessment policy
 * and an auditable provider integration are available.
 */
export function AssessmentCodingPads({
  question, answer, active, working, saving = false, dirty, onChange, onSave,
}: Props) {
  const [tab, setTab] = useState<Pad>(question.language === "sql" ? "sql" : "python");
  const configured = question.language ?? null;
  const editorEnabled = tab !== "ai" && (configured === null || configured === tab);
  const editorLabel = tab === "sql" ? "SQL Pad" : "Python Pad";
  const numberOfLines = Math.min(120, Math.max(10, answer.split("\n").length + 3));

  return (
    <section className="overflow-hidden rounded-xl border border-slate-700 bg-slate-950 text-slate-100"
      aria-label="Assessment coding workspace">
      <header className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-700 bg-slate-900 px-4 py-3">
        <div className="flex flex-wrap gap-2" role="tablist" aria-label="Coding pads">
          {(["python", "sql", "ai"] as const).map((pad) => {
            const enabled = pad === "ai" || configured === null || configured === pad;
            return (
              <button
                key={pad}
                type="button"
                role="tab"
                id={`assessment-tab-${pad}`}
                aria-selected={tab === pad}
                aria-controls="assessment-pad-panel"
                disabled={!enabled}
                onClick={() => setTab(pad)}
                className={
                  "rounded-md px-3 py-2 text-sm font-semibold transition-colors disabled:cursor-not-allowed disabled:opacity-35 " +
                  (tab === pad ? "bg-sky-500 text-slate-950" : "bg-slate-800 text-slate-300 hover:bg-slate-700")
                }
              >
                {pad === "ai" ? "✦ AI Pad" : pad === "python" ? "Python Pad" : "SQL Pad"}
              </button>
            );
          })}
        </div>
        <span className="rounded-full border border-slate-600 px-3 py-1 text-xs text-slate-300">
          {configured === null ? "Legacy code question · language unspecified" : configured === "sql" ? "SQL assessment" : "Python assessment"}
        </span>
      </header>

      <div id="assessment-pad-panel" role="tabpanel" aria-labelledby={`assessment-tab-${tab}`}>
        {tab === "ai" ? (
          <div className="space-y-3 p-6">
            <h3 className="text-lg font-semibold">AI Pad · assessment policy</h3>
            <p className="max-w-2xl text-sm leading-6 text-slate-300">
              AI code hints and answer generation are not enabled in scored employer assessments.
              A consent-based technical interview is available separately below the coding workspace,
              when its provider is configured. It does not supply solutions or grade candidates.
            </p>
            <a className="inline-flex rounded-lg bg-slate-700 px-4 py-2 text-sm font-semibold text-white hover:bg-slate-600"
              href="#assessment-ai-interview">Open optional AI technical interview</a>
          </div>
        ) : editorEnabled ? (
          <div className="space-y-0">
            <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-800 px-4 py-3 text-xs text-slate-400">
              <span>{editorLabel} / answer.{tab === "sql" ? "sql" : "py"}</span>
              <span>{!active ? "Read-only session" : saving ? "Autosaving…" : dirty ? "Unsaved edits" : "Saved to server"}</span>
            </div>
            <div className="grid min-h-[310px] grid-cols-[42px_minmax(0,1fr)]">
              <div aria-hidden="true" className="select-none border-r border-slate-800 bg-slate-900 px-2 pt-4 text-right font-mono text-xs leading-6 text-slate-500">
                {Array.from({ length: numberOfLines }, (_, i) => <div key={i}>{i + 1}</div>)}
              </div>
              <label className="block min-w-0">
                <span className="sr-only">{editorLabel} source response for question {question.number}</span>
                <textarea
                  aria-label={`${editorLabel} source response for question ${question.number}`}
                  value={answer}
                  onChange={(event) => onChange(event.target.value)}
                  disabled={!active || working}
                  rows={Math.max(12, numberOfLines)}
                  maxLength={100_000}
                  spellCheck={false}
                  autoCapitalize="off"
                  autoCorrect="off"
                  className="block w-full resize-y border-0 bg-transparent px-4 py-4 font-mono text-[13px] leading-6 text-emerald-100 outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-sky-500 disabled:opacity-70"
                  placeholder={tab === "sql" ? "-- Enter your SQL query here" : "# Enter your Python solution here"}
                />
              </label>
            </div>
            <footer className="flex flex-wrap items-center justify-between gap-3 border-t border-slate-800 bg-slate-900 px-4 py-3">
              <div className="max-w-xl text-xs leading-5 text-slate-400">
                Python and SQL Run requests use the trusted isolated execution service.
                Save the source before testing. Hidden tests run only after final submission;
                your code never executes in this page.
              </div>
              <button
                type="button"
                disabled={!active || working || saving || !dirty}
                onClick={onSave}
                className="rounded-lg bg-sky-500 px-4 py-2 text-sm font-semibold text-slate-950 disabled:opacity-35"
              >
                {working || saving ? "Saving…" : "Save source response"}
              </button>
            </footer>
          </div>
        ) : (
          <p className="p-6 text-sm text-slate-300">This question requires the {configured?.toUpperCase()} Pad. A different language cannot be submitted for this version.</p>
        )}
      </div>
    </section>
  );
}
