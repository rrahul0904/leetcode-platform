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

  if (readiness.isLoading || submissions.isLoading)
    return (
      <div className="page-content">
        <LoadingState label="Calculating evidence-backed readiness" />
      </div>
    );

  const data = readiness.data;
  const history = submissions.data ?? [];
  const hasEvidence = Boolean(data?.evidence_count);

  return (
    <div className="page-content">
      <PageHeader
        eyebrow="PROGRESS & READINESS"
        title="Your evidence, translated into the next useful move."
        description="Scores come from persisted submissions and versioned deterministic evaluation. Confidence stays separate, so sparse evidence is never presented as certainty."
      />
      {!hasEvidence && (
        <EvidenceNote tone="warning">
          <strong>No evaluated submission exists yet.</strong>
          <span>
            Complete one hosted Python question to establish your first
            competency baseline.
          </span>
        </EvidenceNote>
      )}
      <section className="readiness-grid section-block">
        <article className="readiness-score">
          <CircleGauge size={28} />
          <span>ROLE READINESS</span>
          <strong>{data ? percent(data.overall.score) : "—"}</strong>
          <p>
            {data?.target_role ?? "Staff AI Engineer"} · confidence{" "}
            {data ? percent(data.overall.confidence) : "0%"}
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
              <strong>{data?.competencies.length ?? 0}</strong>
              <span>competencies</span>
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
                <small>{nextAction.data.reasons[0]}</small>
              </span>
              <ArrowRight size={15} />
            </Link>
          ) : (
            <Link className="next-practice-card" href="/question-bank">
              <FileCheck2 size={18} />
              <span>
                <strong>Choose a published question</strong>
                <small>Start with a Python engineering exercise.</small>
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
