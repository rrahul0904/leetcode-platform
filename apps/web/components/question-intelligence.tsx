"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, DatabaseZap, RefreshCw } from "lucide-react";

import {
  EmptyState,
  ErrorState,
  EvidenceNote,
  LoadingState,
  PageHeader,
  SectionHeading,
} from "@/components/page-ui";
import {
  getQuestionIntelligence,
  recomputeCoverageGaps,
  type QuestionIntelligenceMode,
} from "@/lib/api";

const labels: Record<
  QuestionIntelligenceMode,
  { eyebrow: string; title: string; description: string }
> = {
  questions: {
    eyebrow: "HOSTED QUESTION INVENTORY",
    title: "Every draft, review state, and published version.",
    description:
      "This operator view includes non-public records. Candidate delivery remains published-only.",
  },
  families: {
    eyebrow: "CANONICAL FAMILIES",
    title: "Group structure without erasing meaningful differences.",
    description:
      "Families preserve canonical competencies, solution patterns, and controlled variation dimensions.",
  },
  variants: {
    eyebrow: "MEANINGFUL VARIANTS",
    title: "Track requirement-level changes, not superficial rewrites.",
    description:
      "Only records classified as question variations appear in this inventory.",
  },
  gaps: {
    eyebrow: "COVERAGE GAPS",
    title: "Turn missing competency coverage into authoring briefs.",
    description:
      "Gap recomputation uses hosted and external competency mappings and never treats an external link as hosted content.",
  },
  duplicates: {
    eyebrow: "DUPLICATE REVIEW",
    title: "Inspect exact, lexical, structural, solution, and test similarity.",
    description:
      "High similarity blocks publication until originality review is resolved.",
  },
  freshness: {
    eyebrow: "FRESHNESS",
    title: "Keep technical material current after publication.",
    description:
      "Current, review-due, and stale states are derived from the latest hosted-version update.",
  },
  licenses: {
    eyebrow: "RIGHTS INVENTORY",
    title: "Make every hosted-content right auditable.",
    description:
      "Original, organization-owned, and licensed records remain separate from external references.",
  },
  provenance: {
    eyebrow: "PROVENANCE INVENTORY",
    title: "Retain how each hosted package was authored.",
    description:
      "Originality statements, source notes, authoring methods, and hashes survive every import.",
  },
};

function text(value: unknown) {
  if (Array.isArray(value)) return value.join(" · ");
  if (value === null || value === undefined || value === "") return "—";
  return String(value);
}

function rowFor(mode: QuestionIntelligenceMode, item: Record<string, unknown>) {
  if (mode === "families")
    return {
      id: text(item.family_id),
      title: text(item.name),
      detail: `${text(item.member_count)} members · ${text(item.canonical_competency)}`,
      status: "family",
    };
  if (mode === "gaps")
    return {
      id: text(item.gap_id),
      title: text(item.competency_name),
      detail: `${text(item.hosted_count)} hosted · ${text(item.external_reference_count)} external · author ${text(item.recommended_question_count)}`,
      status: text(item.status),
    };
  if (mode === "duplicates")
    return {
      id: text(item.duplicate_id),
      title: text(item.imported_external_id ?? item.imported_slug),
      detail: `${text(item.similarity_score)} similarity · ${text(item.existing_title)}`,
      status: text(item.suggested_action),
    };
  if (mode === "freshness")
    return {
      id: text(item.question_id),
      title: `${text(item.external_id)} · ${text(item.title)}`,
      detail: `${text(item.age_days)} days since update · ${text(item.state)}`,
      status: text(item.freshness_status),
    };
  if (mode === "licenses")
    return {
      id: text(item.question_version_id),
      title: `${text(item.external_id)} · ${text(item.title)}`,
      detail: `${text(item.rights_basis)} · ${text(item.license_identifier)} · ${text(item.provider)}`,
      status: item.expiration_date
        ? `expires ${text(item.expiration_date)}`
        : "no expiry",
    };
  if (mode === "provenance")
    return {
      id: text(item.question_version_id),
      title: `${text(item.external_id)} · ${text(item.title)}`,
      detail: `${text(item.authoring_method)} · ${text(item.originality_statement)}`,
      status: "certified",
    };
  return {
    id: text(item.question_id),
    title: `${text(item.external_id)} · ${text(item.title)}`,
    detail: `${text(item.primary_track)} · ${text(item.difficulty)} · ${text(item.role_level)}`,
    status: text(item.state ?? item.record_type),
  };
}

export function QuestionIntelligence({
  mode,
}: {
  mode: QuestionIntelligenceMode;
}) {
  const queryClient = useQueryClient();
  const query = useQuery({
    queryKey: ["question-intelligence", mode],
    queryFn: ({ signal }) => getQuestionIntelligence(mode, signal),
    retry: false,
  });
  const recompute = useMutation({
    mutationFn: recomputeCoverageGaps,
    onSuccess: async () =>
      queryClient.invalidateQueries({
        queryKey: ["question-intelligence", "gaps"],
      }),
  });
  const copy = labels[mode];
  const rows = (query.data ?? []).map((item) =>
    rowFor(mode, item as unknown as Record<string, unknown>),
  );
  return (
    <div className="page-content">
      <PageHeader
        eyebrow={copy.eyebrow}
        title={copy.title}
        description={copy.description}
      />
      <EvidenceNote>
        <strong>Live PostgreSQL inventory.</strong>
        <span>
          Empty means no qualifying record exists; this page never substitutes
          planning briefs or fabricated counts.
        </span>
      </EvidenceNote>
      <section className="panel section-block">
        <SectionHeading
          eyebrow="CURRENT INVENTORY"
          title={`${rows.length} records`}
          aside={
            mode === "gaps" && (
              <button
                className="button button--ghost"
                onClick={() => recompute.mutate()}
                disabled={recompute.isPending}
              >
                <RefreshCw size={14} /> Recompute gaps
              </button>
            )
          }
        />
        {query.isLoading && <LoadingState label={`Loading ${mode}`} />}
        {query.isError && <ErrorState retry={() => void query.refetch()} />}
        {!query.isLoading && !query.isError && rows.length === 0 && (
          <EmptyState
            title={`No ${mode} records yet.`}
            description="Use the ingestion, source, review, and competency workflows to create evidence-backed records."
          />
        )}
        <div className="roster-list">
          {rows.map((row) => (
            <article className="review-row" key={row.id}>
              <span className="review-row__state">{row.status}</span>
              <DatabaseZap size={17} />
              <div>
                <strong>{row.title}</strong>
                <small>{row.detail}</small>
              </div>
            </article>
          ))}
        </div>
        {recompute.isError && (
          <div className="assignment-ready">
            <AlertTriangle size={18} /> Gap recomputation failed.
          </div>
        )}
      </section>
    </div>
  );
}
