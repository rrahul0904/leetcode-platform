"use client";

import { useQuery } from "@tanstack/react-query";
import {
  ArrowRight,
  CircleGauge,
  FileCheck2,
  History,
  Target,
} from "lucide-react";
import Link from "next/link";

import {
  ErrorState,
  EvidenceNote,
  LoadingState,
  PageHeader,
  SectionHeading,
} from "@/components/page-ui";
import {
  getCandidateReadiness,
  getNextAction,
  getSubmissions,
} from "@/lib/api";

function percent(value: number) {
  return `${Math.round(value * 100)}%`;
}

export function Progress() {
  const readiness = useQuery({
    queryKey: ["candidate-readiness"],
    queryFn: ({ signal }) => getCandidateReadiness(signal),
  });
  const submissions = useQuery({
    queryKey: ["submissions"],
    queryFn: ({ signal }) => getSubmissions(signal),
  });
  const nextAction = useQuery({
    queryKey: ["next-action"],
    queryFn: ({ signal }) => getNextAction(signal),
  });

  if (readiness.isLoading || submissions.isLoading) {
    return (
      <div className="page-content">
        <LoadingState label="Calculating evidence-backed readiness" />
      </div>
    );
  }

  if (readiness.isError || submissions.isError) {
    return (
      <div className="page-content">
        <ErrorState
          retry={() => {
            void readiness.refetch();
            void submissions.refetch();
          }}
        />
      </div>
    );
  }

  const data = readiness.data;
  const history = submissions.data ?? [];
  const hasEvidence = Boolean(data?.evidence_count);

  return (
    <div className="page-content">
      <PageHeader
        eyebrow="READINESS EVIDENCE"
        title="Progress without false certainty."
        description="Your score reflects persisted evaluated submissions and competency evidence. Confidence stays separate, so sparse evidence is never presented as certainty."
      />
      {!hasEvidence && (
        <EvidenceNote tone="warning">
          <strong>No evaluated submission exists yet.</strong>
          <span>
            Complete and submit a runnable published question to establish your first
            competency baseline.
          </span>
        </EvidenceNote>
      )}
      <section className="readiness-grid section-block">
        <article className="readiness-score">
          <CircleGauge size={28} />
          <span>ROLE READINESS</span>
          <strong>{hasEvidence && data ? percent(data.overall.score) : "—"}</strong>
          <p>
            {data?.target_role || "Target role not configured"} · confidence{" "}
            {hasEvidence && data ? percent(data.overall.confidence) : "—"}
          </p>
        </article>
        <div className="panel">
          <SectionHeading eyebrow="EVIDENCE" title="Measured activity" />
          <div className="mini-metrics">
            <div>
              <strong>{history.length}</strong>
              <span>submissions</span>
            </div>
            <div>
              <strong>{data?.evidence_count ?? 0}</strong>
              <span>evidence points</span>
            </div>
            <div>
              <strong>
                {data?.competencies.filter((competency) => competency.evidence_count > 0)
                  .length ?? 0}
              </strong>
              <span>skills with evidence</span>
            </div>
          </div>
          <small>
            Browsing and time-on-page do not count as demonstrated skill.
          </small>
        </div>
        <div className="panel">
          <SectionHeading eyebrow="NEXT ACTION" title="Recommended practice" />
          {nextAction.data ? (
            <Link className="next-practice-card" href={nextAction.data.href}>
              <Target size={18} />
              <span>
                <strong>{nextAction.data.title}</strong>
                <small>{nextAction.data.reasons[0] ?? "Evidence-ranked next step"}</small>
              </span>
              <ArrowRight size={15} />
            </Link>
          ) : nextAction.isError ? (
            <div className="next-practice-card" role="status">
              <FileCheck2 size={18} />
              <span>
                <strong>Recommendation unavailable</strong>
                <small>Your persisted progress is unchanged. Retry when the service is available.</small>
              </span>
            </div>
          ) : (
            <Link className="next-practice-card" href="/question-bank">
              <FileCheck2 size={18} />
              <span>
                <strong>Choose a published question</strong>
                <small>Start with any question that is marked runnable.</small>
              </span>
              <ArrowRight size={15} />
            </Link>
          )}
        </div>
      </section>

      <section className="panel section-block">
        <SectionHeading
          eyebrow="COMPETENCY READINESS"
          title="Score and confidence are shown independently"
        />
        <div className="competency-readiness-list">
          {(data?.competencies ?? []).map((competency) => (
            <article key={competency.competency_id}>
              <div>
                <strong>{competency.name}</strong>
                <small>
                  {competency.evidence_count} evidence · {competency.trend}
                </small>
              </div>
              <div className="readiness-bars">
                <span>
                  <i style={{ width: percent(competency.score) }} />
                </span>
                <small>
                  {percent(competency.score)} score ·{" "}
                  {percent(competency.confidence)} confidence
                </small>
              </div>
            </article>
          ))}
          {!hasEvidence && (
            <p className="empty-copy">
              Competency rows appear after your first evaluated submission.
            </p>
          )}
        </div>
      </section>

      {hasEvidence && data && (
        <section className="detail-grid section-block" aria-label="Readiness interpretation">
          <div className="panel">
            <SectionHeading eyebrow="STRONGEST AREAS" title="Highest-supported competencies" />
            {data.strongest_areas.length ? (
              <div className="competency-readiness-list">
                {data.strongest_areas.map((competency) => (
                  <article key={competency.competency_id}>
                    <div>
                      <strong>{competency.name}</strong>
                      <small>{competency.evidence_count} evidence</small>
                    </div>
                    <b>{percent(competency.score)}</b>
                  </article>
                ))}
              </div>
            ) : (
              <p className="empty-copy">Not enough evidence to identify a strongest area yet.</p>
            )}
          </div>
          <div className="panel">
            <SectionHeading eyebrow="CRITICAL GAPS" title="Skills needing more evidence" />
            {data.critical_gaps.length ? (
              <div className="competency-readiness-list">
                {data.critical_gaps.map((competency) => (
                  <article key={competency.competency_id}>
                    <div>
                      <strong>{competency.name}</strong>
                      <small>
                        {competency.evidence_count} evidence · {competency.trend}
                      </small>
                    </div>
                    <b>{percent(competency.score)}</b>
                  </article>
                ))}
              </div>
            ) : (
              <p className="empty-copy">No critical gap is supported by current evidence.</p>
            )}
          </div>
        </section>
      )}

      <section className="panel section-block">
        <SectionHeading eyebrow="SUBMISSION HISTORY" title="Immutable attempts" />
        <div className="submission-history">
          {history.map((submission) => (
            <article key={submission.id}>
              <History size={16} />
              <div>
                <strong>{submission.question_title}</strong>
                <small>
                  {new Date(submission.submitted_at).toLocaleString()} ·{" "}
                  {submission.runtime}
                </small>
              </div>
              <span className={`status-chip status-chip--${submission.status}`}>
                {submission.status}
              </span>
              <b>{percent(submission.evaluation.overall_score)}</b>
            </article>
          ))}
          {history.length === 0 && (
            <p className="empty-copy">No submission attempts yet.</p>
          )}
        </div>
      </section>
    </div>
  );
}
