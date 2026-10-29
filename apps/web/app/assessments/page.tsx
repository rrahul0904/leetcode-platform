"use client";

import { useEffect, useRef, useState } from "react";

import { AssessmentCodingPads } from "@/components/assessment-coding-pads";
import { AssessmentExecutionReceipt } from "@/components/assessment-execution-receipt";
import { AssessmentQuestionNavigator } from "@/components/assessment-question-navigator";
import { assessmentClockTone, assessmentProgress } from "@/lib/assessment-workspace";
import { nextPendingAssessmentResponse } from "@/lib/assessment-autosave";
import {
  readCandidateInvitationFragment,
  takePendingCandidateInvitation,
} from "@/lib/assessment-invitation-link";
import { EmployerAIInterviewPanel } from "@/components/employer-ai-interview-panel";

import {
  acceptInterviewInvite,
  getInterviewAttempt,
  getCandidateCodeExecution,
  listCandidateCodeExecutionResults,
  queueCandidateCodeExecution,
  listCandidateAssessmentAttempts,
  saveInterviewAnswer,
  submitInterviewAttempt,
  type AssessmentAttempt,
  type CandidateCodeExecution,
} from "@/lib/employer-assessment-api";

const resumeKey = "rigor.assessment.attempt-id";

function formatClock(seconds: number) {
  const safe = Math.max(0, seconds);
  const hours = Math.floor(safe / 3600);
  const minutes = Math.floor((safe % 3600) / 60);
  const secs = safe % 60;
  return [hours, minutes, secs].map((number) => String(number).padStart(2, "0")).join(":");
}

function latestCodeReceipts(
  receipts: CandidateCodeExecution[],
): Record<string, CandidateCodeExecution> {
  const latest: Record<string, CandidateCodeExecution> = {};
  // The backend returns newest first; keep only the latest RUN per question
  // and the unique immutable SUBMIT receipt per question.
  for (const receipt of receipts) {
    const key = receipt.execution_mode + ":" + receipt.question_number;
    if (!(key in latest)) latest[key] = receipt;
  }
  return latest;
}

export default function AssessmentPage() {
  const [invitationId, setInvitationId] = useState("");
  const [secret, setSecret] = useState("");
  const [attempt, setAttempt] = useState<AssessmentAttempt | null>(null);
  const [history, setHistory] = useState<AssessmentAttempt[]>([]);
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [selected, setSelected] = useState(1);
  const [showReview, setShowReview] = useState(false);
  const [now, setNow] = useState(0);
  const [working, setWorking] = useState(false);
  const [autoSaving, setAutoSaving] = useState(false);
  const lastAutoSaveRef = useRef<string | null>(null);
  const [notice, setNotice] = useState("");
  const [codeExecutions, setCodeExecutions] = useState<
    Record<string, CandidateCodeExecution>
  >({});
  const [error, setError] = useState("");

  useEffect(() => {
    // Link secrets are consumed from a URL fragment, never from query params.
    // Remove from history immediately, before any background API requests.
    const fragment = window.location.hash;
    const direct = fragment.startsWith("#invitation=");
    const credentials = direct
      ? readCandidateInvitationFragment(fragment)
      : (() => {
          try {
            return takePendingCandidateInvitation(window.sessionStorage);
          } catch {
            return null;
          }
        })();
    if (direct) {
      window.history.replaceState(
        window.history.state, "", window.location.pathname + window.location.search,
      );
    }
    if (!credentials) {
      if (direct) {
        queueMicrotask(() =>
          setError("This invitation link is invalid. Request a new one-use link."),
        );
      }
      return;
    }
    queueMicrotask(() => {
      setInvitationId(credentials.invitationId);
      setSecret(credentials.acceptanceSecret);
      setNotice("Private invitation loaded. Verify your account and press Start assessment.");
    });
  }, []);

  useEffect(() => {
    const stored = window.sessionStorage.getItem(resumeKey);
    if (!stored) return;
    let cancelled = false;
    void getInterviewAttempt(stored)
      .then((response) => {
        if (cancelled) return;
        setAttempt(response);
        setDrafts(response.answers);
      })
      .catch(() => {
        if (!cancelled) window.sessionStorage.removeItem(resumeKey);
      });
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    let cancelled = false;
    void listCandidateAssessmentAttempts()
      .then((items) => {
        if (!cancelled) setHistory(items);
      })
      .catch(() => {
        // First-time candidates have no history. Invitation entry still works.
      });
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    const attemptId = attempt?.id;
    if (!attemptId) return;
    let cancelled = false;
    queueMicrotask(() => setCodeExecutions({}));
    void listCandidateCodeExecutionResults(attemptId)
      .then((receipts) => {
        if (!cancelled) setCodeExecutions(latestCodeReceipts(receipts));
      })
      .catch(() => {
        // Assessment content remains usable if execution history is down.
        // The candidate may refresh the results without submitting again.
      });
    return () => { cancelled = true; };
  }, [attempt?.id]);

  async function restore(attemptId: string) {
    setWorking(true);
    setError("");
    try {
      const response = await getInterviewAttempt(attemptId);
      setAttempt(response);
      setDrafts(response.answers);
      setSelected(1);
      window.sessionStorage.setItem(resumeKey, response.id);
      setNotice("Assessment restored from your secured candidate history.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to restore assessment.");
    } finally {
      setWorking(false);
    }
  }

  useEffect(() => {
    const interval = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(interval);
  }, []);

  const deadline = attempt?.deadline_at ? new Date(attempt.deadline_at).getTime() : null;
  const secondsLeft = deadline === null ? null : Math.ceil((deadline - now) / 1000);
  const active = attempt?.status === "in_progress" && (secondsLeft ?? 0) > 0;
  const current = attempt?.questions.find((question) => question.number === selected);
  const storedAnswer = current ? attempt?.answers[String(current.number)] ?? "" : "";
  const draftAnswer = current ? drafts[String(current.number)] ?? "" : "";
  const dirty = current ? draftAnswer !== storedAnswer : false;
  const progress = attempt ? assessmentProgress(attempt.questions, attempt.answers, drafts) : null;
  const clockTone = assessmentClockTone(secondsLeft);
  const submitReady = active && !working && !autoSaving && progress?.unsaved === 0;

  // Debounced server-backed autosave works across question navigation. Every
  // changed answer is persisted in turn, not just the currently open question.
  // In-flight saves cannot overwrite a newer typed draft or another attempt.
  useEffect(() => {
    if (!attempt || !active || working || autoSaving) return;
    const attemptId = attempt.id;
    const pending = nextPendingAssessmentResponse(
      attemptId,
      attempt.questions.map((question) => question.number),
      attempt.answers,
      drafts,
      lastAutoSaveRef.current,
    );
    if (!pending) return;
    const revision = pending.revision;

    const timer = window.setTimeout(() => {
      lastAutoSaveRef.current = revision;
      setAutoSaving(true);
      void saveInterviewAnswer(attemptId, pending.number, pending.source)
        .then((updated) => {
          setAttempt((previous) => previous?.id === updated.id ? updated : previous);
          setError("");
        })
        .catch((cause) => {
          setError(
            cause instanceof Error ? "Autosave failed: " + cause.message
              : "Autosave failed. Your unsaved text remains in the editor.",
          );
          // Do not hammer the backend when a save is rejected or unavailable.
          // A changed draft or explicit Save can trigger the next request.
        })
        .finally(() => setAutoSaving(false));
    }, 1400);
    return () => window.clearTimeout(timer);
  }, [attempt, active, drafts, working, autoSaving]);


  // Poll only nonterminal code jobs. The API is authoritative; this page never
  // executes candidate source and never receives private grading fixtures.
  useEffect(() => {
    if (!attempt) return;
    const pending = Object.entries(codeExecutions).filter(
      ([, item]) => !["completed", "failed", "timeout"].includes(item.status),
    );
    if (!pending.length) return;
    let cancelled = false;
    const interval = window.setInterval(() => {
      for (const [key, execution] of pending) {
        void getCandidateCodeExecution(execution.attempt_id, execution.id)
          .then((updated) => {
            if (!cancelled) {
              setCodeExecutions((current) => ({ ...current, [key]: updated }));
            }
          })
          .catch(() => {
            // Outages and authentication errors remain visible when the
            // candidate initiates a new action. Never fabricate a result.
          });
      }
    }, 4000);
    return () => { cancelled = true; window.clearInterval(interval); };
  }, [attempt, codeExecutions]);

  async function queueCode(
    number: number, mode: "RUN" | "SUBMIT", answer: string,
  ) {
    if (!attempt || working) return;
    setWorking(true);
    setError("");
    try {
      if (mode === "RUN") {
        const saved = await saveInterviewAnswer(attempt.id, number, answer);
        setAttempt(saved);
      }
      const key = mode === "SUBMIT"
        ? "final-" + attempt.id + "-" + number
        : "run-" + window.crypto.randomUUID();
      const result = await queueCandidateCodeExecution(attempt.id, number, mode, key);
      setCodeExecutions((current) => ({
        ...current, [mode + ":" + number]: result,
      }));
      setNotice(
        mode === "RUN"
          ? "Sample execution queued. Results appear when the isolated runner completes."
          : "Final hidden-test grading queued. The reviewer can evaluate the result.",
      );
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Coding execution could not be queued.");
    } finally {
      setWorking(false);
    }
  }

  async function acceptInvitation(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (working) return;
    setWorking(true);
    setError("");
    setNotice("");
    try {
      const response = await acceptInterviewInvite(invitationId.trim(), secret.trim());
      setAttempt(response);
      setDrafts(response.answers);
      setSelected(1);
      setSecret("");
      window.sessionStorage.setItem(resumeKey, response.id);
      setNotice("Assessment started. Your deadline is controlled by the server.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not accept invitation.");
    } finally {
      setWorking(false);
    }
  }

  async function save(number: number, value: string) {
    if (!attempt || !active) return;
    setWorking(true);
    setError("");
    try {
      const updated = await saveInterviewAnswer(attempt.id, number, value);
      setAttempt(updated);
      setNotice("Question " + number + " saved.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Answer could not be saved.");
    } finally {
      setWorking(false);
    }
  }

  async function submit() {
    if (!attempt || working) return;
    setWorking(true);
    setError("");
    try {
      const response = await submitInterviewAttempt(attempt.id);
      setAttempt(response);
      setShowReview(false);
      setNotice(
        response.status === "submitted"
          ? "Assessment submitted. Final code grading was queued atomically by the server."
          : "Assessment " + response.status
            + ". Saved answers are retained; final grading was not queued."
      );
      try {
        const receipts = await listCandidateCodeExecutionResults(response.id);
        setCodeExecutions(latestCodeReceipts(receipts));
      } catch {
        setNotice(
          response.status === "submitted"
            ? "Assessment submitted. Final grading was queued by the server; "
              + "refresh to retrieve its execution status."
            : "Assessment " + response.status + ". Saved answers are retained."
        );
      }
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Assessment could not be submitted.");
    } finally {
      setWorking(false);
    }
  }

  return (
    <main className="mx-auto max-w-[1440px] space-y-7 px-4 py-8 sm:px-6 lg:px-8">
      <header className="space-y-2">
        <p className="text-sm font-semibold uppercase tracking-widest text-sky-500">
          SkillForge / Rigor
        </p>
        <h1 className="text-3xl font-bold tracking-tight text-slate-900 sm:text-4xl">Your coding workspace</h1>
        <p className="max-w-3xl text-sm opacity-70">
          Secure candidate workspace. The employer sets the assessment and deadline.
          Interviewer-only solutions and scoring criteria are not visible here.
        </p>
      </header>

      {error && (
        <p role="alert" className="rounded-lg border border-red-500 p-3 text-sm text-red-500">
          {error}
        </p>
      )}
      {notice && (
        <p role="status" className="rounded-lg border border-sky-500 p-3 text-sm">
          {notice}
        </p>
      )}

      {!attempt ? (
        <section className="max-w-xl rounded-2xl border p-6">
          <h2 className="mb-2 text-xl font-semibold">Start your invited assessment</h2>
          <p className="mb-6 text-sm opacity-70">
            Use the invitation ID and secret supplied by the interviewer.
            Your secret is not stored in the browser after acceptance.
          </p>
          <form className="space-y-5" onSubmit={(event) => void acceptInvitation(event)}>
            <label className="block text-sm font-medium">
              Invitation ID
              <input
                aria-label="Invitation ID"
                autoComplete="off"
                required
                value={invitationId}
                onChange={(event) => setInvitationId(event.target.value)}
                className="mt-2 w-full rounded-md border bg-transparent p-3 font-mono text-sm"
              />
            </label>
            <label className="block text-sm font-medium">
              Invitation secret
              <input
                type="password"
                aria-label="Invitation secret"
                autoComplete="off"
                required
                value={secret}
                onChange={(event) => setSecret(event.target.value)}
                className="mt-2 w-full rounded-md border bg-transparent p-3 text-sm"
              />
            </label>
            <button
              disabled={working}
              type="submit"
              className="rounded-lg bg-sky-600 px-5 py-3 font-semibold text-white disabled:opacity-60"
            >
              {working ? "Starting…" : "Start assessment"}
            </button>
          </form>
          {history.length > 0 && (
            <section className="mt-8 space-y-3 border-t pt-6">
              <h3 className="font-semibold">Your previous assessments</h3>
              <p className="text-sm opacity-70">
                Resume a saved assessment on this device without reusing the invitation secret.
              </p>
              {history.map((entry) => (
                <button
                  type="button"
                  key={entry.id}
                  disabled={working}
                  className="block w-full rounded-lg border p-3 text-left text-sm disabled:opacity-40"
                  onClick={() => void restore(entry.id)}
                >
                  <span className="font-semibold">
                    {entry.status === "in_progress" ? "Resume" : "View"} session
                  </span>
                  <span className="ml-2">{entry.status}</span>
                  <span className="mt-1 block break-all font-mono text-xs opacity-65">
                    {entry.id}
                  </span>
                </button>
              ))}
            </section>
          )}
        </section>
      ) : (
        <>
          <button
            type="button"
            className="rounded-lg border px-4 py-2 text-sm"
            onClick={() => {
              setAttempt(null);
              window.sessionStorage.removeItem(resumeKey);
            }}
          >
            Switch assessment
          </button>
          <section className="flex flex-wrap items-center justify-between gap-4 rounded-2xl border border-slate-800 bg-slate-950 p-5 text-white shadow-lg">
            <div>
              <p className="text-sm font-semibold text-sky-300">Live candidate session</p>
              <p className="mt-1 break-all font-mono text-xs text-slate-400">Session {attempt.id}</p>
              <p className="mt-2 text-sm text-slate-300">Status: <strong className="text-white">{attempt.status}</strong>{progress ? " · " + progress.saved + " saved responses" : ""}</p>
            </div>
            <div className="text-right">
              <p className="text-xs uppercase tracking-widest opacity-60">Remaining time</p>
              <p
                className={"font-mono text-3xl font-bold tabular-nums " + (clockTone === "critical" ? "text-rose-400" : clockTone === "warning" ? "text-amber-300" : "text-white")}
                aria-live="off"
              >
                {secondsLeft === null ? "--:--:--" : formatClock(secondsLeft)}
              </p>
              <p className="text-xs text-slate-400">Server deadline is authoritative</p>
            </div>
          </section>

          <div className="grid grid-cols-1 items-start gap-6 lg:grid-cols-[280px_minmax(0,1fr)]">
            {progress && (
              <AssessmentQuestionNavigator progress={progress} selected={selected} onSelect={setSelected} />
            )}

            <article className="min-h-[440px] rounded-2xl border border-slate-200 bg-white p-5 shadow-sm sm:p-7">
              {current && (
                <>
                  <div className="mb-4 flex flex-wrap justify-between gap-3 text-sm text-slate-600">
                    <span className="font-semibold text-sky-700">Question {current.number} of {attempt.questions.length}</span>
                    <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold">{current.marks} points · {current.kind === "code" ? current.language?.toUpperCase() + " coding" : current.kind.replace("_", " ")}</span>
                  </div>
                  <h2 className="mb-6 whitespace-pre-wrap text-xl font-medium">
                    {current.prompt}
                  </h2>
                  {current.kind === "multiple_choice" ? (
                    <fieldset disabled={!active || working} className="space-y-3">
                      <legend className="sr-only">Select one answer</legend>
                      {current.options.map((option, index) => {
                        const letter = String.fromCharCode(65 + index);
                        return (
                          <label key={letter} className="flex cursor-pointer gap-3 rounded-lg border p-4">
                            <input
                              type="radio"
                              name={"question-" + current.number}
                              checked={draftAnswer === letter}
                              onChange={() => setDrafts((previous) => ({
                                ...previous, [String(current.number)]: letter,
                              }))}
                            />
                            <span>{letter}. {option}</span>
                          </label>
                        );
                      })}
                    </fieldset>
                  ) : current.kind === "code" ? (
                    <>
                    <AssessmentCodingPads
                      key={attempt.id + ":" + current.number}
                      question={current}
                      answer={draftAnswer}
                      active={active}
                      working={working}
                      saving={autoSaving}
                      dirty={dirty}
                      onChange={(source) => setDrafts((previous) => ({
                        ...previous, [String(current.number)]: source,
                      }))}
                      onSave={() => void save(current.number, draftAnswer)}
                    />
                    <div className="mt-4 flex flex-wrap items-center gap-3">
                      {active && (
                        <button
                          type="button"
                          disabled={working || autoSaving || !draftAnswer.trim()}
                          onClick={() => void queueCode(current.number, "RUN", draftAnswer)}
                          className="rounded-lg border border-sky-500 px-4 py-2 text-sm disabled:opacity-40"
                        >
                          Run sample tests (Python / SQL)
                        </button>
                      )}
                      {attempt.status === "submitted" &&
                        !codeExecutions["SUBMIT:" + current.number] && (
                          <button
                            type="button"
                            disabled={working}
                            onClick={() => {
                              void listCandidateCodeExecutionResults(attempt.id)
                                .then((receipts) => {
                                  setCodeExecutions(latestCodeReceipts(receipts));
                                })
                                .catch((cause) => {
                                  setError(cause instanceof Error
                                    ? cause.message : "Unable to refresh coding results.");
                                });
                            }}
                            className="rounded-lg border border-sky-500 px-4 py-2 text-sm disabled:opacity-40"
                          >
                            Refresh final grade
                          </button>
                        )}
                    </div>
                    {(["RUN", "SUBMIT"] as const).map((mode) => {
                      const result = codeExecutions[mode + ":" + current.number];
                      return result ? (
                        <AssessmentExecutionReceipt
                          key={mode} mode={mode} receipt={result}
                        />
                      ) : null;
                    })}
                    </>
                  ) : (
                    <div>
                      <label
                        htmlFor="assessment-answer"
                        className="mb-2 block text-sm font-medium"
                      >
                        Written response
                      </label>
                      <textarea
                        id="assessment-answer"
                        disabled={!active || working}
                        rows={15}
                        maxLength={100_000}
                        spellCheck
                        className="w-full rounded-xl border bg-transparent p-4 text-sm"
                        value={draftAnswer}
                        onChange={(event) => setDrafts((previous) => ({
                          ...previous, [String(current.number)]: event.target.value,
                        }))}
                      />
                    </div>
                  )}
                  {current.kind !== "code" && <div className="mt-6 flex flex-wrap items-center gap-3">
                    <button
                      type="button"
                      disabled={!active || working || autoSaving || !dirty}
                      onClick={() => void save(current.number, draftAnswer)}
                      className="rounded-lg bg-sky-600 px-5 py-3 font-semibold text-white disabled:opacity-40"
                    >
                      {working || autoSaving ? "Saving…" : "Save response"}
                    </button>
                    <span className="text-sm opacity-65">
                      {autoSaving ? "Autosaving…" : dirty ? "Unsaved changes" : "Saved to server"}
                    </span>
                  </div>}
                  <div className="mt-8 flex items-center justify-between gap-3 border-t border-slate-100 pt-5">
                    <button type="button" disabled={selected <= 1}
                      onClick={() => setSelected((value) => Math.max(1, value - 1))}
                      className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-semibold text-slate-700 disabled:cursor-not-allowed disabled:opacity-35">
                      Previous question
                    </button>
                    <button type="button" disabled={selected >= attempt.questions.length}
                      onClick={() => setSelected((value) => Math.min(attempt.questions.length, value + 1))}
                      className="rounded-lg bg-slate-900 px-4 py-2 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:opacity-35">
                      Next question
                    </button>
                  </div>
                </>
              )}
            </article>
          </div>
          <section id="assessment-ai-interview" aria-label="Optional AI technical interview">
            <EmployerAIInterviewPanel key={attempt.id} attemptId={attempt.id} active={active} />
          </section>
          <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm" aria-label="Assessment submission">
            <div className="flex flex-wrap items-center justify-between gap-4">
              <div>
                <h2 className="text-lg font-bold text-slate-900">Review your work</h2>
                <p className="mt-1 text-sm text-slate-600">
                  {progress?.answered ?? 0} of {progress?.total ?? 0} questions answered.
                  {progress?.unsaved ? " " + progress.unsaved + " response(s) still unsaved." : " All edits are saved."}
                </p>
              </div>
              <button type="button" disabled={!submitReady || attempt.status !== "in_progress"}
                onClick={() => setShowReview((current) => !current)}
                aria-expanded={showReview} aria-controls="assessment-submit-review"
                className="rounded-xl bg-sky-600 px-5 py-3 text-sm font-bold text-white hover:bg-sky-700 disabled:cursor-not-allowed disabled:opacity-40">
                {showReview ? "Close review" : "Review & submit"}
              </button>
            </div>
            {showReview && progress && (
              <div id="assessment-submit-review" className="mt-5 space-y-4 border-t border-slate-100 pt-5">
                <h3 className="font-semibold text-slate-900">Confirm final submission</h3>
                <p className="text-sm text-slate-600">
                  After submission answers are locked. Coding questions with saved source
                  are queued for server-side private grading. An employer reviewer scores
                  the remaining responses; no automatic hiring decision is made.
                </p>
                <ul className="grid gap-2 sm:grid-cols-2">
                  {progress.questions.map((question) => (
                    <li key={question.number} className="flex items-center justify-between rounded-lg border border-slate-200 p-3 text-sm">
                      <span>Question {question.number}</span>
                      <span className={question.state === "saved" ? "font-semibold text-emerald-700" : "font-semibold text-amber-700"}>
                        {question.state === "saved" ? "Saved" : question.state === "unsaved" ? "Unsaved" : "Unanswered"}
                      </span>
                    </li>
                  ))}
                </ul>
                {progress.unanswered > 0 && (
                  <p role="status" className="rounded-lg bg-amber-50 p-3 text-sm text-amber-900">
                    {progress.unanswered} question(s) have no response. You may still submit, but unanswered questions cannot earn points.
                  </p>
                )}
                <div className="flex flex-wrap gap-3">
                  <button type="button" disabled={!submitReady} onClick={() => void submit()}
                    className="rounded-xl bg-slate-950 px-5 py-3 text-sm font-bold text-white disabled:opacity-40">
                    Confirm & submit assessment
                  </button>
                  <button type="button" onClick={() => setShowReview(false)}
                    className="rounded-xl border border-slate-300 px-5 py-3 text-sm font-semibold text-slate-800">
                    Keep editing
                  </button>
                </div>
              </div>
            )}
          </section>
        </>
      )}
    </main>
  );
}
