"use client";

import { useQuery } from "@tanstack/react-query";
import {
  ArrowRight,
  CheckCircle2,
  CircleX,
  Clock3,
  History,
  LoaderCircle,
} from "lucide-react";
import Link from "next/link";

import { getSubmissions, type CandidateSubmission } from "@/lib/api";

import styles from "./attempt-history.module.css";

function scorePercent(submission: CandidateSubmission) {
  return Math.round(submission.evaluation.overall_score * 100);
}

function statusIcon(status: CandidateSubmission["status"]) {
  if (status === "passed") return <CheckCircle2 size={16} />;
  if (status === "failed" || status === "error") return <CircleX size={16} />;
  return <Clock3 size={16} />;
}

function completedTests(submission: CandidateSubmission) {
  const publicPassed = submission.execution.public_results.filter(
    (item) => item.passed,
  ).length;
  return {
    passed: publicPassed + submission.execution.hidden_passed,
    total: submission.execution.public_results.length + submission.execution.hidden_total,
  };
}

export function AttemptHistory() {
  const submissions = useQuery({
    queryKey: ["candidate-submissions"],
    queryFn: ({ signal }) => getSubmissions(signal),
  });

  if (submissions.isLoading) {
    return (
      <section className={styles.shell}>
        <div className={styles.loading}>
          <LoaderCircle className={styles.spin} size={20} />
          Loading attempt history…
        </div>
      </section>
    );
  }

  if (submissions.isError) {
    return (
      <section className={styles.shell}>
        <div className={styles.error}>
          Attempt history could not be loaded.
          <button onClick={() => void submissions.refetch()} type="button">
            Retry
          </button>
        </div>
      </section>
    );
  }

  const items = submissions.data ?? [];

  return (
    <section className={styles.shell}>
      <header className={styles.hero}>
        <div>
          <span className={styles.eyebrow}>
            <History size={14} /> ATTEMPTS
          </span>
          <h1>Every submission is evidence.</h1>
          <p>
            Review your persisted SkillForge submissions, test outcomes, evaluation
            scores, runtime evidence, and the exact question version that produced them.
          </p>
        </div>
        <div className={styles.summary}>
          <span>Total submissions</span>
          <strong>{items.length}</strong>
          <small>
            {items.filter((item) => item.status === "passed").length} passed
          </small>
        </div>
      </header>

      {items.length === 0 ? (
        <div className={styles.empty}>
          <History size={22} />
          <h2>No completed submissions yet.</h2>
          <p>Start with a published question and submit a solution to create evidence.</p>
          <Link href="/question-bank">
            Open Question Bank <ArrowRight size={15} />
          </Link>
        </div>
      ) : (
        <div className={styles.list}>
          {items.map((submission) => {
            const tests = completedTests(submission);
            return (
              <article className={styles.card} key={submission.id}>
                <div className={styles.status}>
                  {statusIcon(submission.status)}
                  <span>{submission.status}</span>
                </div>

                <div className={styles.problem}>
                  <small>
                    {submission.runtime} · publication {submission.publication_version}
                  </small>
                  <h2>{submission.question_title}</h2>
                  <span>{submission.question_slug}</span>
                </div>

                <div className={styles.metrics}>
                  <div>
                    <strong>{scorePercent(submission)}</strong>
                    <span>score</span>
                  </div>
                  <div>
                    <strong>
                      {tests.passed}/{tests.total}
                    </strong>
                    <span>tests</span>
                  </div>
                  <div>
                    <strong>
                      {submission.execution.runtime_ms == null
                        ? "—"
                        : `${submission.execution.runtime_ms}ms`}
                    </strong>
                    <span>runtime</span>
                  </div>
                </div>

                <div className={styles.breakdown}>
                  <span>
                    Correctness{" "}
                    <strong>
                      {Math.round(submission.evaluation.correctness_score * 100)}
                    </strong>
                  </span>
                  <span>
                    Complexity{" "}
                    <strong>
                      {Math.round(submission.evaluation.complexity_score * 100)}
                    </strong>
                  </span>
                  <span>
                    Quality{" "}
                    <strong>
                      {Math.round(submission.evaluation.code_quality_score * 100)}
                    </strong>
                  </span>
                  <span>
                    Robustness{" "}
                    <strong>
                      {Math.round(submission.evaluation.robustness_score * 100)}
                    </strong>
                  </span>
                </div>

                <footer>
                  <span>
                    Completed {new Date(submission.completed_at).toLocaleString()}
                  </span>
                  <Link href={`/questions/${encodeURIComponent(submission.question_slug)}`}>
                    Revisit question <ArrowRight size={14} />
                  </Link>
                </footer>
              </article>
            );
          })}
        </div>
      )}
    </section>
  );
}
