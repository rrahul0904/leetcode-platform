"use client";

import { useEffect, useState } from "react";
import {
  consentToEmployerAIInterview,
  getEmployerAIInterview,
  sendEmployerAIInterviewMessage,
  withdrawEmployerAIInterview,
  type EmployerAIInterview,
} from "@/lib/employer-assessment-api";

export function EmployerAIInterviewPanel({
  attemptId, active,
}: { attemptId: string; active: boolean }) {
  const [session, setSession] = useState<EmployerAIInterview | null>(null);
  const [agreed, setAgreed] = useState(false);
  const [answer, setAnswer] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    void getEmployerAIInterview(attemptId)
      .then((value) => { if (!cancelled) setSession(value); })
      .catch(() => {});
    return () => { cancelled = true; };
  }, [attemptId]);

  async function begin() {
    if (!agreed || !active || busy) return;
    setBusy(true);
    setError("");
    try {
      setSession(await consentToEmployerAIInterview(attemptId));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to start interview");
    } finally {
      setBusy(false);
    }
  }

  async function send(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!active || !session || busy || !answer.trim()) return;
    setBusy(true);
    setError("");
    try {
      setSession(await sendEmployerAIInterviewMessage(
        attemptId, answer.trim(), crypto.randomUUID(),
      ));
      setAnswer("");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Interviewer unavailable");
    } finally {
      setBusy(false);
    }
  }

  async function withdraw() {
    if (!session || busy) return;
    setBusy(true);
    setError("");
    try {
      setSession(await withdrawEmployerAIInterview(attemptId));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Withdrawal failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section aria-label="Optional AI technical interview" className="space-y-4 rounded-2xl border p-6">
      <h2 className="text-xl font-semibold">Optional text-based AI interview</h2>
      <p className="text-sm opacity-70">
        This opt-in service sends your technical interview messages to the configured
        model provider and stores a transcript. It asks follow-up questions only.
        Evaluation and employment decisions require separate human review.
      </p>
      {error && <p role="alert" className="rounded-lg border p-3 text-sm">{error}</p>}
      {!session ? (
        <div className="space-y-3">
          <label className="flex gap-3 text-sm">
            <input type="checkbox" checked={agreed}
              onChange={(event) => setAgreed(event.target.checked)} />
            I agree to the use and retention of my interview text for this assessment.
          </label>
          <button type="button" disabled={!agreed || !active || busy}
            onClick={() => void begin()} className="rounded-lg border px-4 py-2 disabled:opacity-40">
            Opt in to AI interview
          </button>
        </div>
      ) : (
        <div className="space-y-4">
          <p className="text-sm">Session: {session.status}, turns: {session.turn_count}/12</p>
          {session.messages.map((item) => (
            <div key={item.sequence_number} className="rounded-lg border p-3">
              <strong className="text-xs">{item.role}</strong>
              <p className="whitespace-pre-wrap text-sm">{item.content}</p>
            </div>
          ))}
          {!session.provider_configured && session.status === "active" && (
            <p role="status" className="text-sm">
              The model provider is not configured; regular assessment answers remain available.
            </p>
          )}
          {session.status === "active" && active && session.provider_configured && (
            <form onSubmit={(event) => void send(event)} className="space-y-3">
              <label htmlFor="ai-interview-reply" className="block text-sm">
                Technical response
              </label>
              <textarea id="ai-interview-reply" maxLength={2000} rows={4}
                value={answer} disabled={busy}
                onChange={(event) => setAnswer(event.target.value)}
                className="w-full rounded-lg border bg-transparent p-3" />
              <button type="submit" disabled={busy || !answer.trim()}
                className="rounded-lg border px-4 py-2 disabled:opacity-40">
                {busy ? "Loading next question..." : "Send"}
              </button>
            </form>
          )}
          {session.status === "active" && (
            <button type="button" onClick={() => void withdraw()}
              disabled={busy} className="rounded-lg border px-4 py-2 disabled:opacity-40">
              Withdraw consent for further model calls
            </button>
          )}
          <p className="text-xs opacity-60">
            Withdrawal prevents further processing but does not erase existing records.
          </p>
        </div>
      )}
    </section>
  );
}
