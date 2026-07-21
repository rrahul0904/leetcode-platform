"use client";

import { useQuery } from "@tanstack/react-query";
import {
  ArrowUpRight,
  ChevronLeft,
  ChevronRight,
  ExternalLink,
  Search,
  SlidersHorizontal,
} from "lucide-react";
import { useDeferredValue, useState } from "react";

import { EmptyState, ErrorState, PageHeader } from "@/components/page-ui";
import {
  getExternalReferenceFacets,
  getExternalReferences,
  type ExternalReference,
} from "@/lib/api";

export function ExternalReferenceCard({
  reference,
}: {
  reference: ExternalReference;
}) {
  const type = reference.coverage_level.includes("OPEN_LICENSE")
    ? "OPEN SOURCE"
    : reference.coverage_level.includes("LICENSED")
      ? "LICENSED"
      : "EXTERNAL";
  const concepts = Array.from(
    new Set([
      ...reference.competency_slugs,
      ...reference.patterns,
      ...reference.topic_metadata,
    ]),
  ).slice(0, 5);
  return (
    <article className="question-card external-card">
      <div className="question-card__topline">
        <span className="practice-type practice-type--external">{type}</span>
        <span
          className={`difficulty difficulty--${reference.difficulty ?? "unrated"}`}
        >
          {reference.difficulty ?? "Unrated"}
        </span>
      </div>
      <span className="question-id">{reference.source_name}</span>
      <h3>{reference.title ?? "Untitled source reference"}</h3>
      <p>
        {reference.abstract ??
          "Practice metadata indexed from the source. The original prompt remains on the source site."}
      </p>
      <div className="skill-row">
        {concepts.map((concept) => (
          <span key={concept}>{concept}</span>
        ))}
      </div>
      <dl className="external-card__meta">
        <div>
          <dt>Access</dt>
          <dd>{reference.access_tier.replaceAll("_", " ")}</dd>
        </div>
        <div>
          <dt>Availability</dt>
          <dd>{reference.source_availability}</dd>
        </div>
      </dl>
      <a
        className="button button--dark external-card__action"
        href={reference.canonical_url}
        target="_blank"
        rel="noopener noreferrer"
      >
        Open on source <ArrowUpRight size={15} />
      </a>
    </article>
  );
}

export function ExternalCatalog({
  showHeader = false,
  pageSize = 12,
}: {
  showHeader?: boolean;
  pageSize?: number;
}) {
  const [query, setQuery] = useState("");
  const deferredQuery = useDeferredValue(query);
  const [sourceId, setSourceId] = useState("");
  const [difficulty, setDifficulty] = useState("");
  const [competency, setCompetency] = useState("");
  const [page, setPage] = useState(1);
  const facets = useQuery({
    queryKey: ["external-reference-facets"],
    queryFn: ({ signal }) => getExternalReferenceFacets(signal),
  });
  const references = useQuery({
    queryKey: [
      "external-references",
      deferredQuery,
      sourceId,
      difficulty,
      competency,
      page,
      pageSize,
    ],
    queryFn: ({ signal }) =>
      getExternalReferences(
        {
          query: deferredQuery,
          sourceId,
          difficulty,
          competency,
          page,
          pageSize,
        },
        signal,
      ),
  });
  const totalPages = references.data
    ? Math.max(1, Math.ceil(references.data.total / pageSize))
    : 1;
  const update = (work: () => void) => {
    work();
    setPage(1);
  };
  const clear = () => {
    setQuery("");
    setSourceId("");
    setDifficulty("");
    setCompetency("");
    setPage(1);
  };
  return (
    <>
      {showHeader && (
        <PageHeader
          eyebrow="EXTERNAL PRACTICE"
          title="Explore the source-backed practice catalog."
          description="Search legally indexed metadata and continue to the canonical source. External references are never presented as internally executable questions."
        />
      )}
      <section
        className="catalog-toolbar"
        aria-label="External practice filters"
      >
        <label className="search-field">
          <Search size={18} />
          <span className="sr-only">Search external practice</span>
          <input
            value={query}
            onChange={(event) => update(() => setQuery(event.target.value))}
            placeholder="Search titles, topics, or patterns"
          />
        </label>
        <label>
          <span className="sr-only">Source</span>
          <select
            value={sourceId}
            onChange={(event) => update(() => setSourceId(event.target.value))}
          >
            <option value="">All sources</option>
            {facets.data?.sources.map((item) => (
              <option value={item.value} key={item.value}>
                {item.label} ({item.count})
              </option>
            ))}
          </select>
        </label>
        <label>
          <span className="sr-only">Difficulty</span>
          <select
            value={difficulty}
            onChange={(event) =>
              update(() => setDifficulty(event.target.value))
            }
          >
            <option value="">All difficulties</option>
            {facets.data?.difficulties.map((item) => (
              <option value={item.value} key={item.value}>
                {item.label} ({item.count})
              </option>
            ))}
          </select>
        </label>
        <label>
          <span className="sr-only">Competency</span>
          <select
            value={competency}
            onChange={(event) =>
              update(() => setCompetency(event.target.value))
            }
          >
            <option value="">All topics</option>
            {facets.data?.competencies.map((item) => (
              <option value={item.value} key={item.value}>
                {item.label} ({item.count})
              </option>
            ))}
          </select>
        </label>
        <button className="button button--ghost button--icon" onClick={clear}>
          <SlidersHorizontal size={16} /> Reset
        </button>
      </section>
      <div className="catalog-summary">
        <span>
          {references.data
            ? `${references.data.total.toLocaleString()} external practice references`
            : "Reading PostgreSQL catalog…"}
        </span>
        <span>
          Page {page} of {totalPages}
        </span>
      </div>
      {(references.isError || facets.isError) && (
        <ErrorState
          retry={() => {
            void references.refetch();
            void facets.refetch();
          }}
        />
      )}
      {references.isLoading && (
        <div className="question-grid" aria-label="Loading external practice">
          {Array.from({ length: pageSize }, (_, index) => (
            <div className="question-card question-card--loading" key={index} />
          ))}
        </div>
      )}
      {references.data?.items.length === 0 && (
        <EmptyState
          title="No external references match these filters."
          description="Try a broader search or clear the source, topic, and difficulty filters."
          action={
            <button className="button button--dark" onClick={clear}>
              Clear filters
            </button>
          }
        />
      )}
      {references.data && references.data.items.length > 0 && (
        <div className="question-grid">
          {references.data.items.map((reference) => (
            <ExternalReferenceCard
              reference={reference}
              key={reference.reference_id}
            />
          ))}
        </div>
      )}
      {references.data && references.data.total > pageSize && (
        <nav className="pagination" aria-label="External catalog pages">
          <button
            className="button button--ghost"
            disabled={page === 1}
            onClick={() => setPage((value) => Math.max(1, value - 1))}
          >
            <ChevronLeft size={16} /> Previous
          </button>
          <span>
            {((page - 1) * pageSize + 1).toLocaleString()}–
            {Math.min(page * pageSize, references.data.total).toLocaleString()}{" "}
            of {references.data.total.toLocaleString()}
          </span>
          <button
            className="button button--dark"
            disabled={!references.data.has_next}
            onClick={() => setPage((value) => value + 1)}
          >
            Next <ChevronRight size={16} />
          </button>
        </nav>
      )}
    </>
  );
}

export function ExternalPractice() {
  return (
    <div className="page-content">
      <ExternalCatalog showHeader />
    </div>
  );
}
