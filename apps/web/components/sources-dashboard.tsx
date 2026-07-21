"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Activity,
  Ban,
  CheckCircle2,
  Database,
  Link2,
  Plus,
  Radar,
  RefreshCw,
  ShieldCheck,
} from "lucide-react";
import { type FormEvent, useMemo, useState } from "react";

import {
  EmptyState,
  ErrorState,
  EvidenceNote,
  LoadingState,
  PageHeader,
  SectionHeading,
} from "@/components/page-ui";
import {
  getCompetencyCoverage,
  getContinuousCoverage,
  getSources,
  registerSource,
  reviewSource,
  verifySource,
  type SourceRegistryRecord,
} from "@/lib/api";

export function SourcesDashboard({ view = "all" }: { view?: string }) {
  const client = useQueryClient();
  const sources = useQuery({
    queryKey: ["sources", view],
    queryFn: ({ signal }) =>
      getSources(
        view === "approved"
          ? { connectorStatus: "approved" }
          : view === "blocked"
            ? { coverageLevel: "BLOCKED" }
            : view === "discovered"
              ? { connectorStatus: "unreviewed" }
              : {},
        signal,
      ),
    retry: false,
  });
  const coverage = useQuery({
    queryKey: ["continuous-coverage"],
    queryFn: ({ signal }) => getContinuousCoverage(signal),
    retry: false,
  });
  const competencies = useQuery({
    queryKey: ["competency-coverage"],
    queryFn: ({ signal }) => getCompetencyCoverage(signal),
    retry: false,
  });
  const [notice, setNotice] = useState("");
  const mutate = useMutation({
    mutationFn: async (work: () => Promise<unknown>) => work(),
    onSuccess: async () => {
      setNotice("The source registry was updated and audited.");
      await client.invalidateQueries({ queryKey: ["sources"] });
      await client.invalidateQueries({ queryKey: ["continuous-coverage"] });
    },
    onError: () =>
      setNotice(
        "The source operation was rejected. Verify rights, coverage, and connector approval constraints.",
      ),
  });

  if (sources.isLoading || coverage.isLoading)
    return (
      <div className="page-content">
        <LoadingState label="Reading the continuous source registry" />
      </div>
    );
  return (
    <div className="page-content">
      <PageHeader
        eyebrow="CONTINUOUS CONTENT INTELLIGENCE"
        title="Monitor sources without confusing links with hosted questions."
        description="Every source starts unreviewed. Rights review determines whether the platform may discover, deep-link, index metadata, or host explicitly licensed content."
      />
      <EvidenceNote>
        <strong>No fixed question ceiling.</strong>
        <span>
          The 1,350-item manifest is the hosted launch foundation. Sources,
          external references, hosted questions, and executable exercises retain
          separate counters indefinitely.
        </span>
      </EvidenceNote>
      {notice && (
        <div className="assignment-ready">
          <ShieldCheck size={20} />
          <div>
            <strong>Registry result</strong>
            <p>{notice}</p>
          </div>
        </div>
      )}
      {(sources.isError || coverage.isError) && (
        <ErrorState
          retry={() => {
            void sources.refetch();
            void coverage.refetch();
          }}
        />
      )}
      {coverage.data && (
        <section
          className="status-strip"
          aria-label="Continuous coverage counters"
        >
          <Metric
            label="Discovered sources"
            value={coverage.data.discovered_sources}
            icon={Radar}
          />
          <Metric
            label="Approved connectors"
            value={coverage.data.approved_sources}
            icon={CheckCircle2}
          />
          <Metric
            label="External references"
            value={coverage.data.external_references}
            icon={Link2}
          />
          <Metric
            label="Published hosted"
            value={coverage.data.published_questions}
            icon={Database}
          />
        </section>
      )}
      <section className="reviewer-layout section-block">
        <RegisterSource
          busy={mutate.isPending}
          submit={(work) => mutate.mutate(work)}
        />
        <div className="panel panel--wide">
          <SectionHeading
            eyebrow={`${view.toUpperCase()} SOURCES`}
            title={`${sources.data?.length ?? 0} registry records`}
          />
          {sources.data?.length === 0 && (
            <EmptyState
              title="No sources match this view."
              description="Register a source or select another registry state."
            />
          )}
          <div className="roster-list">
            {sources.data?.map((source) => (
              <SourceRow
                source={source}
                key={source.source_id}
                busy={mutate.isPending}
                run={(work) => mutate.mutate(work)}
              />
            ))}
          </div>
        </div>
      </section>
      <section className="panel section-block">
        <SectionHeading
          eyebrow="GLOBAL ONTOLOGY"
          title="Competency coverage"
          aside={
            <span className="status-chip">
              {competencies.data?.length ?? 0} competencies
            </span>
          }
        />
        <div className="distribution-list">
          {competencies.data?.slice(0, 28).map((item) => (
            <div key={item.competency_id}>
              <span>{item.name}</span>
              <div>
                <i
                  style={{
                    width: `${Math.max(2, item.coverage_score * 100)}%`,
                  }}
                />
              </div>
              <strong>
                {item.hosted_question_count}H · {item.external_reference_count}E
              </strong>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}

function Metric({
  label,
  value,
  icon: Icon,
}: {
  label: string;
  value: number;
  icon: typeof Radar;
}) {
  return (
    <div className="stat stat--accent">
      <Icon size={17} />
      <span>{label}</span>
      <strong>{value.toLocaleString()}</strong>
      <small>authoritative record count</small>
    </div>
  );
}

function RegisterSource({
  busy,
  submit,
}: {
  busy: boolean;
  submit: (work: () => Promise<unknown>) => void;
}) {
  const [name, setName] = useState("");
  const [domain, setDomain] = useState("");
  function register(event: FormEvent) {
    event.preventDefault();
    submit(() =>
      registerSource({
        source_name: name,
        canonical_domain: domain,
        source_category: "administrator-submission",
        discovery_method: "administrator-submission",
        access_method: "manual_review",
        priority: 50,
      }),
    );
  }
  return (
    <div className="panel">
      <SectionHeading
        eyebrow="SOURCE DISCOVERY"
        title="Register before collection"
      />
      <form className="reviewer-form" onSubmit={register}>
        <label>
          <span>Source name</span>
          <input
            value={name}
            onChange={(event) => setName(event.target.value)}
            required
          />
        </label>
        <label>
          <span>Canonical domain</span>
          <input
            value={domain}
            onChange={(event) => setDomain(event.target.value)}
            placeholder="example.org"
            required
          />
        </label>
        <button className="button button--primary" disabled={busy}>
          <Plus size={15} /> Register discovery-only
        </button>
      </form>
      <div className="policy-list">
        <div>
          <span>01</span>
          <p>Unreviewed sources cannot synchronize automatically.</p>
        </div>
        <div>
          <span>02</span>
          <p>Metadata records never count as hosted practice questions.</p>
        </div>
        <div>
          <span>03</span>
          <p>Full content requires verified rights evidence.</p>
        </div>
      </div>
    </div>
  );
}

function SourceRow({
  source,
  busy,
  run,
}: {
  source: SourceRegistryRecord;
  busy: boolean;
  run: (work: () => Promise<unknown>) => void;
}) {
  const canVerify = source.connector_status === "approved";
  const reviewPayload = useMemo(
    () => ({
      rights_status: "metadata_permitted" as const,
      coverage_level: "METADATA_ONLY" as const,
      collection_mode: "manual-metadata-feed",
      connector_status: "approved" as const,
      connector_type: "manual-metadata-feed",
      connector_configuration: {},
      review_notes:
        "Administrator verified that only public metadata and canonical links may be collected.",
    }),
    [],
  );
  return (
    <article className="review-row">
      <span className="review-row__state">
        {source.connector_status === "approved" ? (
          <Activity size={14} />
        ) : source.coverage_level === "BLOCKED" ? (
          <Ban size={14} />
        ) : (
          <Radar size={14} />
        )}{" "}
        {source.connector_status}
      </span>
      <div>
        <span className="question-id">{source.canonical_domain}</span>
        <strong>{source.source_name}</strong>
        <small>
          {source.source_category} · {source.coverage_level} ·{" "}
          {source.actual_indexed_volume.toLocaleString()} indexed
        </small>
        <div className="skill-row">
          {source.connector_status === "unreviewed" && (
            <button
              className="button button--ghost"
              disabled={busy}
              onClick={() =>
                run(() => reviewSource(source.source_id, reviewPayload))
              }
            >
              <ShieldCheck size={14} /> Approve metadata only
            </button>
          )}
          {canVerify && (
            <button
              className="button button--ghost"
              disabled={busy}
              onClick={() => run(() => verifySource(source.source_id))}
            >
              <RefreshCw size={14} /> Verify now
            </button>
          )}
        </div>
      </div>
      <span className="status-chip">Priority {source.priority}</span>
    </article>
  );
}
