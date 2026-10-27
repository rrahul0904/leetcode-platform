"use client";

import { useEffect, useState } from "react";

import {
  acceptInterviewInvite,
  getInterviewAttempt,
  saveInterviewAnswer,
  submitInterviewAttempt,
  type AssessmentAttempt,
} from "@/lib/employer-assessment-api";

const resumeKey = "rigor.assessment.attempt-id";

function formatClock(seconds: number) {
  const safe = Math.max(0, seconds);
  const hours = Math.floor(safe / 3600);
  const minutes = Math.floor((safe % 3600) / 60);
  const secs = safe % 60;
  return [hours, minutes, secs].map((number) => String(number).padStart(2, "0")).join(":");
}

export default function AssessmentPage() {
  const [invitationId, setInvitationId] = useState("");
  const [secret, setSecret] = useState("");
  const [attempt, setAttempt] = useState<AssessmentAttempt | null>(null);
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [selected, setSelected] = useState(1);
  const [now, setNow] = useState(0);
  const [working, setWorking] = useState(false);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");

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
    if (!attempt || !active || !value.trim()) return;
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
    if (!window.confirm("Submit this assessment? You cannot edit answers afterwards.")) {
      return;
    }
    setWorking(true);
    setError("");
    try {
      const response = await submitInterviewAttempt(attempt.id);
      setAttempt(response);
      setNotice("Assessment " + response.status + ". Your answers are saved.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Assessment could not be submitted.");
    } finally {
      setWorking(false);
    }
  }

  return (
    <main className="mx-auto max-w-6xl space-y-8 px-4 py-10">
      <header className="space-y-2">
        <p className="text-sm font-semibold uppercase tracking-widest text-sky-500">
          SkillForge / Rigor
        </p>
        <h1 className="text-3xl font-semibold tracking-tight">Technical Assessment</h1>
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
          <h2 className="mb-2 text-xl font-semibold">Enter your invitation</h2>
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
        </section>
      ) : (
        <>
          <section className="flex flex-wrap items-center justify-between gap-4 rounded-2xl border p-5">
            <div>
              <p className="text-sm opacity-60">Candidate assessment session</p>
              <p className="font-mono text-xs">{attempt.id}</p>
              <p className="mt-2 text-sm">Status: <strong>{attempt.status}</strong></p>
            </div>
            <div className="text-right">
              <p className="text-xs uppercase tracking-widest opacity-60">Remaining time</p>
              <p
                className="font-mono text-3xl font-semibold tabular-nums"
                aria-live="off"
              >
                {secondsLeft === null ? "--:--:--" : formatClock(secondsLeft)}
              </p>
              <p className="text-xs opacity-60">Server deadline is authoritative</p>
            </div>
          </section>

          <div className="grid grid-cols-1 gap-6 lg:grid-cols-[220px_minmax(0,1fr)]">
            <nav aria-label="Assessment questions" className="rounded-2xl border p-4">
              <h2 className="mb-4 font-semibold">Questions</h2>
              <div className="grid grid-cols-4 gap-2 lg:grid-cols-2">
                {attempt.questions.map((question) => (
                  <button
                    key={question.number}
                    type="button"
                    onClick={() => setSelected(question.number)}
                    aria-current={question.number === selected ? "step" : undefined}
                    className={
                      "rounded-lg border p-3 text-sm " +
                      (question.number === selected ? "border-sky-500 font-semibold" : "")
                    }
                  >
                    Q{question.number}
                    {attempt.answers[String(question.number)] ? " ✓" : ""}
                  </button>
                ))}
              </div>
            </nav>

            <article className="min-h-[440px] rounded-2xl border p-6">
              {current && (
                <>
                  <div className="mb-4 flex flex-wrap justify-between gap-3 text-sm opacity-70">
                    <span>Question {current.number} of {attempt.questions.length}</span>
                    <span>{current.marks} marks · {current.kind.replace("_", " ")}</span>
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
                  ) : (
                    <div>
                      <label
                        htmlFor="assessment-answer"
                        className="mb-2 block text-sm font-medium"
                      >
                        {current.kind === "code" ? "Source code" : "Written response"}
                      </label>
                      <textarea
                        id="assessment-answer"
                        disabled={!active || working}
                        rows={15}
                        maxLength={100_000}
                        spellCheck={current.kind !== "code"}
                        className={
                          "w-full rounded-xl border bg-transparent p-4 text-sm " +
                          (current.kind === "code" ? "font-mono" : "")
                        }
                        value={draftAnswer}
                        onChange={(event) => setDrafts((previous) => ({
                          ...previous, [String(current.number)]: event.target.value,
                        }))}
                      />
                      {current.kind === "code" && (
                        <p className="mt-2 text-xs opacity-60">
                          Code execution is not yet enabled in this assessment workspace.
                          Save your source response for reviewer evaluation.
                        </p>
                      )}
                    </div>
                  )}
                  <div className="mt-6 flex flex-wrap items-center gap-3">
                    <button
                      type="button"
                      disabled={!active || working || !dirty || !draftAnswer.trim()}
                      onClick={() => void save(current.number, draftAnswer)}
                      className="rounded-lg bg-sky-600 px-5 py-3 font-semibold text-white disabled:opacity-40"
                    >
                      {working ? "Saving…" : "Save response"}
                    </button>
                    <span className="text-sm opacity-65">
                      {dirty ? "Unsaved changes" : "Saved to server"}
                    </span>
                  </div>
                </>
              )}
            </article>
          </div>
          <section className="flex flex-wrap items-center justify-between gap-4 rounded-xl border p-5">
            <p className="text-sm opacity-70">
              Submit only after saving each response. The server rejects changes after submission.
            </p>
            <button
              type="button"
              disabled={!active || working || Object.keys(drafts).some(
                (key) => drafts[key] !== (attempt.answers[key] ?? ""),
              )}
              onClick={() => void submit()}
              className="rounded-lg border border-sky-500 px-5 py-3 font-semibold disabled:opacity-40"
            >
              Submit assessment
            </button>
          </section>
        </>
      )}
    </main>
  );
}
