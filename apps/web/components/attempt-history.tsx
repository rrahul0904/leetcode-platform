"use client";

import { useQuery } from "@tanstack/react-query";
import { CheckCircle2, CircleAlert, Clock3, Code2 } from "lucide-react";
import Link from "next/link";

import { getSubmissions } from "@/lib/api";

function formatDate(value: string) {
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

export function AttemptHistory() {
  const attempts = useQuery({
    queryKey: ["submissions", "attempt-history"],
    queryFn: ({ signal }) => getSubmissions(signal),
  });

  return (
    <div className="attempt-history-page">
      <header>
        <span className="kb-eyebrow">ATTEMPT HISTORY</span>
        <h1>Review the evidence behind your readiness.</h1>
        <p>
          This view contains candidate-safe submission summaries only. Hidden test inputs,
          expected outputs, evaluator source, and privileged execution logs are never exposed.
        </p>
      </header>

      {attempts.isLoading && (
        <div className="kb-workspace-loading">Loading submission history…</div>
      )}
      {attempts.isError && (
        <div className="kb-message">
          <strong>Attempt history could not be loaded.</strong>
          <button type="button" onClick={() => void attempts.refetch()}>
            Try again
          </button>
        </div>
      )}
      {attempts.data && attempts.data.length === 0 && (
        <div className="kb-message">
          <Code2 size={22} />
          <strong>No graded submissions yet.</strong>
          <Link className="kb-primary-action" href="/problems?availability=runnable">
            Find a runnable question
          </Link>
        </div>
      )}
      {attempts.data && attempts.data.length > 0 && (
        <section className="attempt-history-list" aria-label="Submission attempts">
          {attempts.data.map((attempt) => {
            const passed = attempt.status === "passed";
            return (
              <article key={attempt.id}>
                <div className={passed ? "is-passed" : "is-failed"}>
                  {passed ? <CheckCircle2 size={18} /> : <CircleAlert size={18} />}
                  <strong>{attempt.status.toUpperCase()}</strong>
                </div>
                <div>
                  <small>{attempt.question_slug}</small>
                  <h2>{attempt.question_title}</h2>
                  <p>
                    {attempt.runtime.toUpperCase()} · publication {attempt.publication_version}
                  </p>
                </div>
                <div className="attempt-history-score">
                  <strong>{Math.round(attempt.evaluation.overall_score * 100)}%</strong>
                  <span>overall</span>
                </div>
                <div className="attempt-history-meta">
                  <span>
                    <Clock3 size={13} /> {formatDate(attempt.completed_at)}
                  </span>
                  <span>{attempt.execution.runtime_ms ?? 0} ms</span>
                </div>
                <Link href={`/practice/${attempt.question_slug}`}>Practice again →</Link>
              </article>
            );
          })}
        </section>
      )}
    </div>
  );
}
