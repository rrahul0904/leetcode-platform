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
import { getCatalogStatus, runApprovedCollectors } from "@/lib/api";

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
  if (status.isLoading) {
    return (
      <div className="page-content">
        <LoadingState label="Reading catalog synchronization state" />
      </div>
    );
  }
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
      {status.isError && <ErrorState retry={() => void status.refetch()} />}
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
