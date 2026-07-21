"use client";

import { useQuery } from "@tanstack/react-query";
import {
  ArrowRight,
  CircleGauge,
  Compass,
  FileCheck2,
  LockKeyhole,
  Route,
} from "lucide-react";
import Link from "next/link";

import { EvidenceNote, PageHeader, SectionHeading } from "@/components/page-ui";
import { getContentStats } from "@/lib/api";
import { titleCaseSlug } from "@/lib/product-data";

export function Progress() {
  const stats = useQuery({
    queryKey: ["content-stats"],
    queryFn: ({ signal }) => getContentStats(signal),
  });
  const distributions = Object.entries(stats.data?.track_counts ?? {}).sort(
    (a, b) => b[1] - a[1],
  );
  const maximum = Math.max(1, ...distributions.map(([, count]) => count));
  return (
    <div className="page-content">
      <PageHeader
        eyebrow="PROGRESS & READINESS"
        title="Measure evidence, not activity theater."
        description="Candidate performance metrics begin after authenticated practice and published content exist. Today this surface reports platform readiness and gives you the next honest action."
      />
      <EvidenceNote tone="warning">
        <strong>No candidate readiness score exists yet.</strong>
        <span>
          Rigor will not infer skill from browsing planned briefs or generate a
          synthetic percentage without submission evidence.
        </span>
      </EvidenceNote>
      <section className="readiness-grid section-block">
        <article className="readiness-score">
          <CircleGauge size={28} />
          <span>CANDIDATE EVIDENCE</span>
          <strong>Not measured</strong>
          <p>
            Requires published questions, authenticated submissions, and
            calibrated rubrics.
          </p>
        </article>
        <div className="panel">
          <SectionHeading eyebrow="CONTENT PIPELINE" title="Availability" />
          <div className="mini-metrics">
            <div>
              <strong>
                {stats.data?.foundation_manifest_entries.toLocaleString() ??
                  "—"}
              </strong>
              <span>launch briefs</span>
            </div>
            <div>
              <strong>{stats.data?.complete_questions ?? "—"}</strong>
              <span>complete</span>
            </div>
            <div>
              <strong>{stats.data?.published_questions ?? "—"}</strong>
              <span>published</span>
            </div>
          </div>
          <div className="progress-track progress-track--large">
            <i
              style={{
                width: `${Math.min(100, ((stats.data?.published_questions ?? 0) / Math.max(1, stats.data?.foundation_manifest_entries ?? 1)) * 100)}%`,
              }}
            />
          </div>
          <small>
            Launch-foundation benchmark only; ingestion continues without a
            final ceiling.
          </small>
        </div>
        <div className="panel">
          <SectionHeading
            eyebrow="NEXT ACTIONS"
            title="Build useful evidence"
          />
          <div className="action-list">
            <Link href="/learning-paths">
              <Route size={17} />
              <span>
                <strong>Select a learning path</strong>
                <small>Define the target sequence</small>
              </span>
              <ArrowRight size={14} />
            </Link>
            <Link href="/design-lab">
              <Compass size={17} />
              <span>
                <strong>Create a design artifact</strong>
                <small>Practice structured reasoning locally</small>
              </span>
              <ArrowRight size={14} />
            </Link>
            <Link href="/content-review">
              <FileCheck2 size={17} />
              <span>
                <strong>Advance the first package</strong>
                <small>Unblock candidate practice</small>
              </span>
              <ArrowRight size={14} />
            </Link>
          </div>
        </div>
      </section>
      <section className="panel section-block">
        <SectionHeading
          eyebrow="BANK COVERAGE"
          title="Planned allocation by track"
        />
        <div className="distribution-list">
          {distributions.map(([track, count]) => (
            <div key={track}>
              <span>{titleCaseSlug(track)}</span>
              <div>
                <i style={{ width: `${(count / maximum) * 100}%` }} />
              </div>
              <strong>{count}</strong>
            </div>
          ))}
        </div>
      </section>
      <section className="locked-metrics section-block">
        <LockKeyhole size={20} />
        <div>
          <strong>
            Submission analytics are locked by evidence dependencies.
          </strong>
          <p>
            Accuracy trends, hint use, spaced repetition, role readiness, and
            difficulty calibration will appear only after the execution and
            evaluation planes generate defensible data.
          </p>
        </div>
      </section>
    </div>
  );
}
