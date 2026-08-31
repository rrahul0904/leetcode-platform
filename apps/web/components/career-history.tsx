"use client";

import { useCallback, useEffect, useState } from "react";

import {
  listCareerJobs,
  type CareerJobStatus,
  type CareerJobSummary,
  updateCareerJobStatus,
} from "@/lib/career-api";

import styles from "./career-history.module.css";

const STATUSES: Array<{ value: CareerJobStatus; label: string }> = [
  { value: "saved", label: "Saved" },
  { value: "tailored", label: "Tailored" },
  { value: "applied", label: "Applied" },
  { value: "screen", label: "Recruiter screen" },
  { value: "interview", label: "Interview" },
  { value: "offer", label: "Offer" },
  { value: "rejected", label: "Rejected" },
  { value: "withdrawn", label: "Withdrawn" },
];

function dateLabel(value: string | null) {
  if (!value) return "Not analyzed";
  const date = new Date(value);
  return Number.isNaN(date.valueOf())
    ? "Recently analyzed"
    : new Intl.DateTimeFormat(undefined, {
        month: "short",
        day: "numeric",
        year: "numeric",
      }).format(date);
}

export function CareerHistory() {
  const [jobs, setJobs] = useState<CareerJobSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [updatingJobId, setUpdatingJobId] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const result = await listCareerJobs();
      setJobs(result);
      setError(null);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "CareerOS history could not load.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    void listCareerJobs(controller.signal)
      .then((result) => {
        setJobs(result);
        setError(null);
      })
      .catch((caught: unknown) => {
        if (controller.signal.aborted) return;
        setError(caught instanceof Error ? caught.message : "CareerOS history could not load.");
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });

    function onHistoryChanged() {
      void refresh();
    }

    window.addEventListener("careeros:history-changed", onHistoryChanged);
    return () => {
      controller.abort();
      window.removeEventListener("careeros:history-changed", onHistoryChanged);
    };
  }, [refresh]);

  async function changeStatus(job: CareerJobSummary, status: CareerJobStatus) {
    if (job.status === status || updatingJobId) return;
    setUpdatingJobId(job.id);
    setError(null);
    try {
      const updated = await updateCareerJobStatus(job.id, status);
      setJobs((current) => current.map((item) => (item.id === updated.id ? updated : item)));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "CareerOS status could not update.");
    } finally {
      setUpdatingJobId(null);
    }
  }

  return (
    <section className={styles.section} aria-labelledby="career-history-title">
      <header className={styles.header}>
        <div>
          <p className={styles.eyebrow}>CareerOS · Application history</p>
          <h2 id="career-history-title">Your active job search</h2>
          <p>Every analysis is retained as candidate-owned history and can move through the funnel.</p>
        </div>
        <span className={styles.count}>{jobs.length} target roles</span>
      </header>

      {error && <p className={styles.error}>{error}</p>}
      {loading ? (
        <div className={styles.empty}>Loading your CareerOS history…</div>
      ) : jobs.length === 0 ? (
        <div className={styles.empty}>
          Your first analyzed role will appear here automatically. Re-analyzing the same job keeps
          one job record while adding a new versioned analysis.
        </div>
      ) : (
        <div className={styles.grid}>
          {jobs.map((job) => (
            <article className={styles.card} key={job.id}>
              <div className={styles.topline}>
                <div>
                  <h3 className={styles.title}>{job.job_title || "Target role"}</h3>
                  <p className={styles.company}>{job.company || "Company not specified"}</p>
                </div>
                <div className={styles.score}>
                  <strong>{job.latest_fit_score ?? "—"}</strong>
                  <span>fit / 100</span>
                </div>
              </div>

              <div className={styles.meta}>
                <span>{job.analysis_count} analyses</span>
                <span>Last analyzed {dateLabel(job.last_analyzed_at)}</span>
                <span>{job.missing_skills.length} named gaps</span>
              </div>

              {job.missing_skills.length > 0 && (
                <div className={styles.chips} aria-label="Missing skills">
                  {job.missing_skills.slice(0, 5).map((skill) => (
                    <span className={styles.chip} key={skill}>
                      {skill}
                    </span>
                  ))}
                </div>
              )}

              <div className={styles.controls}>
                <label htmlFor={`career-status-${job.id}`}>Application stage</label>
                <select
                  className={styles.select}
                  disabled={updatingJobId === job.id}
                  id={`career-status-${job.id}`}
                  onChange={(event) =>
                    void changeStatus(job, event.target.value as CareerJobStatus)
                  }
                  value={job.status}
                >
                  {STATUSES.map((status) => (
                    <option key={status.value} value={status.value}>
                      {status.label}
                    </option>
                  ))}
                </select>
              </div>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}