"use client";

import { useEffect, useState } from "react";

import {
  getEmployerAttempt,
  getEmployerAssessmentReport,
  downloadEmployerAssessmentCSV,
  getEmployerInterviewTranscript,
  listEmployerAssessments,
  listEmployerAttempts,
  listEmployerCodeExecutionResults,
  provisionalMCQScore,
  submitEmployerHumanReview,
  type EmployerAssessment,
  type CandidateCodeExecution,
  type EmployerAttemptDetail,
  type EmployerAttemptSummary,
  type EmployerAssessmentReport,
  type EmployerTranscript,
  type HumanQuestionScore,
  type SubmittedHumanReview,
  type ProvisionalMCQScore,
} from "@/lib/employer-assessment-api";

export default function EmployerReviewWorkspace() {
  const [assessments, setAssessments] = useState<EmployerAssessment[]>([]);
  const [assessmentId, setAssessmentId] = useState("");
  const [attempts, setAttempts] = useState<EmployerAttemptSummary[]>([]);
  const [report, setReport] = useState<EmployerAssessmentReport | null>(null);
  const [transcript, setTranscript] = useState<EmployerTranscript | null>(null);
  const [detail, setDetail] = useState<EmployerAttemptDetail | null>(null);
  const [scores, setScores] = useState<Record<number, HumanQuestionScore>>({});
  const [overallNotes, setOverallNotes] = useState("");
  const [result, setResult] = useState<SubmittedHumanReview | null>(null);
  const [provisional, setProvisional] = useState<ProvisionalMCQScore | null>(null);
  const [codeExecutions, setCodeExecutions] = useState<CandidateCodeExecution[]>([]);
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
    setReport(null);
    setTranscript(null);
    setScores({});
    setResult(null);
    setProvisional(null);
    setCodeExecutions([]);
    if (!id) {
      setAttempts([]);
      return;
    }
    setBusy(true);
    setError("");
    try {
      const [items, summary] = await Promise.all([
        listEmployerAttempts(id), getEmployerAssessmentReport(id),
      ]);
      setAttempts(items);
      setReport(summary);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to load attempts.");
    } finally {
      setBusy(false);
    }
  }

  async function openAttempt(id: string) {
    setTranscript(null);
    setBusy(true);
    setError("");
    setResult(null);
    setProvisional(null);
    setCodeExecutions([]);
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
      if (response.attempt.status === "submitted") {
        try {
          setTranscript(await getEmployerInterviewTranscript(response.attempt.id));
        } catch {
          setTranscript(null);
        }
        try {
          const codeReceipts = await listEmployerCodeExecutionResults(response.attempt.id);
          setCodeExecutions(codeReceipts);
        } catch {
          setCodeExecutions([]);
        }
        try {
          const scored = await provisionalMCQScore(response.attempt.id);
          setProvisional(scored);
        } catch {
          // Rubric keys may not exist on legacy written-only assessments.
          // Human review stays available and does not infer an automatic score.
          setProvisional(null);
        }
      }
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to load evidence.");
    } finally {
      setBusy(false);
    }
  }

  async function downloadCSV() {
    if (!assessmentId || busy) return;
    setBusy(true);
    setError("");
    try {
      const file = await downloadEmployerAssessmentCSV(assessmentId);
      const url = URL.createObjectURL(file);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = "skillforge-assessment-" + assessmentId + ".csv";
      anchor.click();
      window.setTimeout(() => URL.revokeObjectURL(url), 1_000);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to export assessment CSV.");
    } finally {
      setBusy(false);
    }
  }

  async function submit() {
    if (!detail || busy || detail.attempt.status !== "submitted") return;
    setBusy(true);
    setError("");
    try {
      const scoresToSubmit = detail.questions
        .map((question) => scores[question.number])
        .filter((score): score is HumanQuestionScore => score !== undefined);
      if (scoresToSubmit.length !== detail.questions.length) {
        throw new Error("Every question needs a completed reviewer score.");
      }
      const submitted = await submitEmployerHumanReview(
        detail.attempt.id,
        scoresToSubmit,
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

      {report && (
        <section className="space-y-4 rounded-2xl border p-6">
          <div className="flex flex-wrap justify-between gap-3">
            <div>
              <h2 className="text-xl font-semibold">Employer assessment dashboard</h2>
              <p className="text-sm opacity-70">Signed human reviews only. No automatic hiring decisions.</p>
            </div>
            <button type="button" disabled={busy} onClick={() => void downloadCSV()}
              className="rounded-lg border px-4 py-2 text-sm disabled:opacity-40">
              Download scorecards (CSV)
            </button>
          </div>
          <div className="grid gap-3 sm:grid-cols-4">
            {([
              ["Invited", report.total_invitations],
              ["Started", report.total_attempts],
              ["Submitted", report.submitted_attempts],
              ["Human reviewed", report.human_reviewed_attempts],
            ] as const).map(([label, value]) => (
              <div key={label} className="rounded-xl border p-4">
                <p className="text-xs opacity-60">{label}</p>
                <p className="mt-2 text-2xl font-semibold">{value}</p>
              </div>
            ))}
          </div>
        </section>
      )}

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
          {transcript && (
            <section className="space-y-3 rounded-xl border p-5">
              <h3 className="font-semibold">Consented AI interview transcript</h3>
              <p className="text-sm opacity-65">
                {transcript.turns.length} messages · {transcript.status}
              </p>
              {transcript.turns.map((item) => (
                <div key={item.sequence_number} className="rounded-lg border p-4">
                  <p className="text-xs font-semibold uppercase">{item.role}</p>
                  <p className="mt-2 whitespace-pre-wrap text-sm">{item.content}</p>
                </div>
              ))}
            </section>
          )}
          {provisional && (
            <div className="space-y-2 rounded-xl border p-5">
              <h3 className="font-semibold">Objective questions — provisional evidence</h3>
              <p className="text-lg font-mono">
                {provisional.mcq_awarded_marks} / {provisional.mcq_maximum_marks} MCQ marks
              </p>
              <p className="text-sm opacity-70">
                {provisional.human_review_pending_marks} marks still require human evaluation.
                This receipt is version-bound and does not determine hiring.
                Human reviewers must score every question independently below.
              </p>
            </div>
          )}
          {codeExecutions.length > 0 && (
            <section className="space-y-3 rounded-xl border p-5">
              <div className="flex flex-wrap justify-between gap-3">
                <h3 className="font-semibold">Isolated Python/SQL execution evidence</h3>
                <button
                  type="button"
                  disabled={busy}
                  onClick={() => void openAttempt(detail.attempt.id)}
                  className="rounded-lg border px-3 py-2 text-sm disabled:opacity-40"
                >
                  Refresh code results
                </button>
              </div>
              <p className="text-sm opacity-70">
                Results are version-bound and advisory to the signed human review.
                Hidden test inputs and expected outputs are never displayed.
              </p>
              {codeExecutions.map((execution) => (
                <div key={execution.id} className="rounded-lg border p-3 text-sm">
                  <p>
                    Question {execution.question_number} · {execution.language.toUpperCase()}
                    {" · "}{execution.execution_mode} · {execution.status}
                  </p>
                  {execution.status === "completed" &&
                    execution.execution_mode === "SUBMIT" && (
                    <p className="mt-1 font-semibold">
                      {execution.awarded_marks ?? "Pending"} objective points ·
                      {" "}{execution.hidden_passed ?? 0} /
                      {execution.hidden_total ?? 0} hidden cases passed
                    </p>
                  )}
                  {execution.runtime_ms !== null && (
                    <p className="mt-1 text-xs opacity-65">
                      Runtime {execution.runtime_ms} ms ·
                      Receipt {execution.id.slice(0, 12)}
                    </p>
                  )}
                </div>
              ))}
            </section>
          )}
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
