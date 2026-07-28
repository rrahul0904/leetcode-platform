"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  CheckCircle2,
  Database,
  RefreshCw,
  ShieldCheck,
  TriangleAlert,
} from "lucide-react";

import {
  EmptyState,
  ErrorState,
  LoadingState,
  PageHeader,
} from "@/components/page-ui";
import {
  getCatalogStatus,
  getContentImports,
  getPracticeSummary,
  getPublishedQuestions,
  getReviewQueue,
  runApprovedCollectors,
} from "@/lib/api";

function formatDate(value: string | null) {
  return value ? new Date(value).toLocaleString() : "Never";
}

export function CatalogStatus() {
  const client = useQueryClient();
  const status = useQuery({
    queryKey: ["catalog-status"],
    queryFn: ({ signal }) => getCatalogStatus(signal),
    retry: false,
  });
  const summary = useQuery({
    queryKey: ["practice-summary"],
    queryFn: ({ signal }) => getPracticeSummary(signal),
    retry: false,
  });
  const imports = useQuery({
    queryKey: ["content-imports"],
    queryFn: ({ signal }) => getContentImports(signal),
    retry: false,
  });
  const reviews = useQuery({
    queryKey: ["review-queue"],
    queryFn: ({ signal }) => getReviewQueue(signal),
    retry: false,
  });
  const published = useQuery({
    queryKey: ["catalog-status-published"],
    queryFn: ({ signal }) =>
      getPublishedQuestions(
        {
          query: "",
          track: "",
          skill: "",
          difficulty: "",
          role: "",
          companyStyle: "",
          completionStatus: "",
          sort: "title",
          page: 1,
          pageSize: 100,
        },
        signal,
      ),
    retry: false,
  });
  const collector = useMutation({
    mutationFn: runApprovedCollectors,
    onSuccess: async () => {
      await Promise.all([
        client.invalidateQueries({ queryKey: ["catalog-status"] }),
        client.invalidateQueries({ queryKey: ["practice-summary"] }),
        client.invalidateQueries({ queryKey: ["external-references"] }),
      ]);
    },
  });
  if (
    status.isLoading ||
    summary.isLoading ||
    imports.isLoading ||
    reviews.isLoading ||
    published.isLoading
  ) {
    return (
      <div className="page-content">
        <LoadingState label="Reading catalog synchronization state" />
      </div>
    );
  }
  const importFailures =
    imports.data?.reduce((total, item) => total + item.rejected_count, 0) ?? 0;
  const trackCounts = Object.entries(
    (published.data?.items ?? []).reduce<Record<string, number>>(
      (counts, question) => ({
        ...counts,
        [question.track]: (counts[question.track] ?? 0) + 1,
      }),
      {},
    ),
  ).sort(([left], [right]) => left.localeCompare(right));
  const difficultyCounts = Object.entries(
    (published.data?.items ?? []).reduce<Record<string, number>>(
      (counts, question) => ({
        ...counts,
        [question.difficulty]: (counts[question.difficulty] ?? 0) + 1,
      }),
      {},
    ),
  );
  return (
    <div className="page-content">
      <PageHeader
        eyebrow="CATALOG STATUS"
        title="Approved connector health and collection evidence."
        description="Each row is backed by the source registry and its latest PostgreSQL synchronization run."
        actions={
          <button
            className="button button--primary"
            disabled={collector.isPending}
            onClick={() => collector.mutate()}
          >
            <RefreshCw
              size={16}
              className={collector.isPending ? "spin" : undefined}
            />
            {collector.isPending ? "Collecting…" : "Run approved collectors"}
          </button>
        }
      />
      {collector.isSuccess && (
        <div className="assignment-ready">
          <CheckCircle2 size={20} />
          <div>
            <strong>Collection completed</strong>
            <p>
              {collector.data.external_references.toLocaleString()} external
              references are indexed.
            </p>
          </div>
        </div>
      )}
      {collector.isError && (
        <div className="assignment-ready assignment-ready--warning">
          <TriangleAlert size={20} />
          <div>
            <strong>Collection failed</strong>
            <p>
              The backend collector returned an error. Inspect the API logs and
              retry.
            </p>
          </div>
        </div>
      )}
      {(status.isError ||
        summary.isError ||
        imports.isError ||
        reviews.isError ||
        published.isError) && (
        <ErrorState
          retry={() => {
            void status.refetch();
            void summary.refetch();
            void imports.refetch();
            void reviews.refetch();
            void published.refetch();
          }}
        />
      )}
      {summary.data && (
        <section
          className="metric-grid section-block"
          aria-label="Catalog totals"
        >
          {[
            ["Hosted packages", summary.data.hosted_records],
            ["Published hosted", summary.data.published_hosted_questions],
            ["External references", summary.data.external_references],
            ["Approved sources", summary.data.approved_sources],
            [
              "Review backlog",
              reviews.data?.length ?? summary.data.awaiting_review,
            ],
            ["Import failures", importFailures],
          ].map(([label, value]) => (
            <article className="metric-card" key={label}>
              <span>{label}</span>
              <strong>{Number(value).toLocaleString()}</strong>
            </article>
          ))}
          <article className="metric-card">
            <span>Last collection</span>
            <strong>
              {formatDate(summary.data.last_successful_collection)}
            </strong>
          </article>
        </section>
      )}
      {(trackCounts.length > 0 || difficultyCounts.length > 0) && (
        <section className="catalog-breakdown-grid section-block">
          <article className="panel">
            <h2>Published content by track</h2>
            <dl className="catalog-status-list">
              {trackCounts.map(([track, count]) => (
                <div key={track}>
                  <dt>{track.replaceAll("-", " ")}</dt>
                  <dd>{count}</dd>
                </div>
              ))}
            </dl>
          </article>
          <article className="panel">
            <h2>Published content by difficulty</h2>
            <dl className="catalog-status-list">
              {difficultyCounts.map(([difficulty, count]) => (
                <div key={difficulty}>
                  <dt>{difficulty}</dt>
                  <dd>{count}</dd>
                </div>
              ))}
            </dl>
          </article>
        </section>
      )}
      {status.data?.length === 0 && (
        <EmptyState
          title="No source records exist."
          description="Seed the source registry before collecting metadata."
        />
      )}
      <div className="catalog-status-grid section-block">
        {status.data?.map((source) => (
          <article className="panel catalog-status-card" key={source.source_id}>
            <div className="question-card__topline">
              <span
                className={`status-chip status-chip--${source.connector_status}`}
              >
                {source.connector_status}
              </span>
              {source.failures ? (
                <TriangleAlert size={17} />
              ) : (
                <ShieldCheck size={17} />
              )}
            </div>
            <span className="question-id">{source.canonical_domain}</span>
            <h3>{source.source_name}</h3>
            <dl className="catalog-status-list">
              <div>
                <dt>Last run</dt>
                <dd>{formatDate(source.last_run)}</dd>
              </div>
              <div>
                <dt>References collected</dt>
                <dd>{source.references_collected.toLocaleString()}</dd>
              </div>
              <div>
                <dt>References updated</dt>
                <dd>{source.references_updated.toLocaleString()}</dd>
              </div>
              <div>
                <dt>Failures</dt>
                <dd>{source.failures}</dd>
              </div>
              <div>
                <dt>Rights</dt>
                <dd>{source.rights_status.replaceAll("_", " ")}</dd>
              </div>
              <div>
                <dt>Coverage</dt>
                <dd>{source.coverage_level.replaceAll("_", " ")}</dd>
              </div>
            </dl>
            {source.last_error && (
              <p className="catalog-error">{source.last_error}</p>
            )}
            <div className="catalog-next-action">
              <Database size={15} />
              <span>
                <small>NEXT ACTION</small>
                <strong>{source.next_available_action}</strong>
              </span>
            </div>
          </article>
        ))}
      </div>
    </div>
  );
}
