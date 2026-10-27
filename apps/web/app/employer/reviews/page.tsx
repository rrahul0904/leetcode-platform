"use client";

import { useEffect, useState } from "react";

import {
  getEmployerAttempt,
  listEmployerAssessments,
  listEmployerAttempts,
  submitEmployerHumanReview,
  type EmployerAssessment,
  type EmployerAttemptDetail,
  type EmployerAttemptSummary,
  type HumanQuestionScore,
  type SubmittedHumanReview,
} from "@/lib/employer-assessment-api";

export default function EmployerReviewWorkspace() {
  const [assessments, setAssessments] = useState<EmployerAssessment[]>([]);
  const [assessmentId, setAssessmentId] = useState("");
  const [attempts, setAttempts] = useState<EmployerAttemptSummary[]>([]);
  const [detail, setDetail] = useState<EmployerAttemptDetail | null>(null);
  const [scores, setScores] = useState<Record<number, HumanQuestionScore>>({});
  const [overallNotes, setOverallNotes] = useState("");
  const [result, setResult] = useState<SubmittedHumanReview | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    void listEmployerAssessments()
      .then((items) => { if (active) setAssessments(items); })
      .catch((cause: unknown) => {
        if (active) {
          setError(cause instanceof Error ? cause.message : "Unable to list assessments.");
        }
      });
    return () => { active = false; };
  }, []);

  async function loadAttempts(id: string) {
    setAssessmentId(id);
    setDetail(null);
    setScores({});
    setResult(null);
    if (!id) {
      setAttempts([]);
      return;
    }
    setBusy(true);
    setError("");
    try {
      setAttempts(await listEmployerAttempts(id));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to load attempts.");
    } finally {
      setBusy(false);
    }
  }

  async function openAttempt(id: string) {
    setBusy(true);
    setError("");
    setResult(null);
    try {
      const response = await getEmployerAttempt(id);
      setDetail(response);
      setScores(Object.fromEntries(response.questions.map((question) => [
        question.number,
        {
          question_number: question.number,
          awarded_marks: 0,
          evidence_note: "",
        },
      ])));
      setOverallNotes("");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to load evidence.");
    } finally {
      setBusy(false);
    }
  }

  async function submit() {
    if (!detail || busy || detail.attempt.status !== "submitted") return;
    setBusy(true);
    setError("");
    try {
      const submitted = await submitEmployerHumanReview(
        detail.attempt.id,
        detail.questions.map((question) => scores[question.number]),
        overallNotes.trim(),
      );
      setResult(submitted);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Review could not be submitted.");
    } finally {
      setBusy(false);
    }
  }

  const complete = !!detail && detail.questions.every((question) => {
    const score = scores[question.number];
    return score !== undefined
      && Number.isInteger(score.awarded_marks)
      && score.awarded_marks >= 0
      && score.awarded_marks <= question.marks
      && score.evidence_note.trim().length >= 10;
  }) && overallNotes.trim().length >= 15;

  return (
    <main className="mx-auto max-w-6xl space-y-8 px-4 py-10">
      <header>
        <p className="text-sm font-semibold uppercase tracking-widest text-sky-500">
          SkillForge / Rigor · Employer
        </p>
        <h1 className="mt-2 text-3xl font-semibold">Human assessment review</h1>
        <p className="mt-2 max-w-3xl text-sm opacity-70">
          Review submitted candidate answers against the published question version.
          Every question requires an explicit score and evidence note. No AI or automated
          hiring decision is produced by this workspace.
        </p>
      </header>

      {error && (
        <p role="alert" className="rounded-lg border border-red-500 p-4 text-red-500">
          {error}
        </p>
      )}
      {result && (
        <section role="status" className="space-y-2 rounded-lg border border-sky-500 p-4">
          <strong>Human review submitted</strong>
          <p>
            {result.awarded_marks} / {result.maximum_marks} marks. This is an
            assessment review, not a hiring decision.
          </p>
          <p className="break-all font-mono text-xs">Receipt {result.review_id}</p>
        </section>
      )}

      <section className="grid gap-4 rounded-2xl border p-6 sm:grid-cols-2">
        <label className="text-sm">
          Assessment
          <select
            aria-label="Select employer assessment"
            className="mt-2 w-full rounded-lg border bg-transparent p-3"
            value={assessmentId}
            onChange={(event) => void loadAttempts(event.target.value)}
          >
            <option value="">Choose an assessment</option>
            {assessments.map((assessment) => (
              <option key={assessment.id} value={assessment.id}>
                {assessment.title} · v{assessment.version}
              </option>
            ))}
          </select>
        </label>
        <label className="text-sm">
          Candidate attempt
          <select
            aria-label="Select candidate attempt"
            className="mt-2 w-full rounded-lg border bg-transparent p-3"
            value={detail?.attempt.id ?? ""}
            disabled={busy || !assessmentId}
            onChange={(event) => void openAttempt(event.target.value)}
          >
            <option value="">Choose an attempt</option>
            {attempts.map((attempt) => (
              <option key={attempt.id} value={attempt.id}>
                {attempt.candidate_id.slice(0, 8)} · {attempt.status} · {attempt.id.slice(0, 8)}
              </option>
            ))}
          </select>
        </label>
      </section>

      {detail && (
        <section className="space-y-6">
          <div className="flex flex-wrap justify-between gap-3 rounded-xl border p-5">
            <div>
              <h2 className="text-lg font-semibold">Submitted candidate evidence</h2>
              <p className="text-sm opacity-70">
                Status: {detail.attempt.status} · maximum {detail.maximum_marks} marks
              </p>
            </div>
            <p className="max-w-sm break-all font-mono text-xs opacity-65">
              Source version SHA-256: {detail.content_sha256}
            </p>
          </div>
          {detail.questions.map((question) => {
            const score = scores[question.number];
            const answer = detail.answers.find(
              (item) => item.question_number === question.number,
            );
            return (
              <article key={question.number} className="space-y-4 rounded-2xl border p-6">
                <div className="flex flex-wrap justify-between gap-3">
                  <h3 className="font-semibold">Question {question.number}</h3>
                  <span className="text-sm opacity-70">
                    {question.kind} · {question.marks} marks
                  </span>
                </div>
                <p className="whitespace-pre-wrap">{question.prompt}</p>
                <div className="rounded-lg border p-4">
                  <strong className="text-sm">Candidate response</strong>
                  <pre className="mt-3 whitespace-pre-wrap break-words text-sm">
                    {answer?.answer_text ?? "(No response submitted)"}
                  </pre>
                </div>
                {score && (
                  <div className="grid gap-4 sm:grid-cols-[140px_minmax(0,1fr)]">
                    <label className="text-sm">
                      Awarded marks
                      <input
                        type="number"
                        min={0}
                        max={question.marks}
                        value={score.awarded_marks}
                        disabled={busy || !!result || detail.attempt.status !== "submitted"}
                        className="mt-2 w-full rounded-lg border bg-transparent p-3"
                        onChange={(event) => {
                          const awarded_marks = Number(event.target.value);
                          setScores((previous) => ({
                            ...previous,
                            [question.number]: { ...score, awarded_marks },
                          }));
                        }}
                      />
                    </label>
                    <label className="text-sm">
                      Evidence note (required)
                      <textarea
                        value={score.evidence_note}
                        minLength={10}
                        rows={3}
                        maxLength={2000}
                        disabled={busy || !!result || detail.attempt.status !== "submitted"}
                        className="mt-2 w-full rounded-lg border bg-transparent p-3"
                        onChange={(event) => setScores((previous) => ({
                          ...previous,
                          [question.number]: {
                            ...score, evidence_note: event.target.value,
                          },
                        }))}
                      />
                    </label>
                  </div>
                )}
              </article>
            );
          })}
          <section className="space-y-4 rounded-xl border p-6">
            <label className="block text-sm">
              Overall reviewer notes
              <textarea
                rows={4} minLength={15} maxLength={4000}
                value={overallNotes}
                disabled={busy || !!result || detail.attempt.status !== "submitted"}
                className="mt-2 w-full rounded-lg border bg-transparent p-3"
                onChange={(event) => setOverallNotes(event.target.value)}
              />
            </label>
            <p className="text-sm opacity-70">
              Current review score:{" "}
              {Object.values(scores).reduce((total, item) => total + item.awarded_marks, 0)}
              {" "}/ {detail.maximum_marks}. Each review is immutable after submission.
            </p>
            <button
              type="button"
              disabled={busy || !complete || !!result || detail.attempt.status !== "submitted"}
              className="rounded-lg bg-sky-600 px-5 py-3 font-semibold text-white disabled:opacity-40"
              onClick={() => void submit()}
            >
              {busy ? "Submitting…" : "Submit signed human review"}
            </button>
          </section>
        </section>
      )}
    </main>
  );
}
