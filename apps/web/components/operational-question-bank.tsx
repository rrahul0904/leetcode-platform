"use client";

import { useQuery } from "@tanstack/react-query";
import {
  ArrowRight,
  Building2,
  CheckCircle2,
  Clock3,
  Code2,
  ExternalLink,
  FileText,
  Search,
  SlidersHorizontal,
} from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";

import {
  type Availability,
  getKnowledgeCatalogStats,
  getKnowledgeCompanies,
  getKnowledgeProblems,
} from "@/lib/knowledge-api";

const difficulties = ["", "easy", "medium", "hard"] as const;
const languages = ["", "python", "javascript", "sql"] as const;
const availabilities: Array<[Availability | "", string]> = [
  ["", "All availability"],
  ["runnable", "Runnable in Rigor"],
  ["hosted", "Hosted prompt"],
  ["in_review", "In review"],
  ["reference_only", "External reference"],
];
const sorts = [
  ["relevance", "Recommended"],
  ["frequency", "Company frequency"],
  ["difficulty", "Difficulty"],
  ["newest", "Recently added"],
  ["title", "A–Z"],
] as const;

export function availabilityLabel(value: Availability) {
  return {
    runnable: "Runnable",
    hosted: "Hosted",
    in_review: "In review",
    reference_only: "Reference only",
  }[value];
}

function availabilityAction(value: Availability) {
  return {
    runnable: "Open coding pad",
    hosted: "Open prompt",
    in_review: "Review details",
    reference_only: "Open reference",
  }[value];
}

function displayDifficulty(value: string | null) {
  if (!value) return "Unrated";
  return value.charAt(0).toUpperCase() + value.slice(1);
}

export function OperationalQuestionBank() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const filters = {
    query: searchParams.get("query") ?? "",
    difficulty: searchParams.get("difficulty") ?? "",
    language: searchParams.get("language") ?? "",
    company: searchParams.get("company") ?? "",
    topic: searchParams.get("topic") ?? "",
    availability: (searchParams.get("availability") ?? "") as Availability | "",
    sort: searchParams.get("sort") ?? "relevance",
    page: Number(searchParams.get("page") ?? "1"),
  };

  function setFilter(name: string, value: string) {
    const next = new URLSearchParams(searchParams.toString());
    if (value) next.set(name, value);
    else next.delete(name);
    if (name !== "page") next.delete("page");
    const query = next.toString();
    router.replace(query ? `${pathname}?${query}` : pathname, { scroll: false });
  }

  const problems = useQuery({
    queryKey: ["operational-knowledge-problems", filters],
    queryFn: ({ signal }) =>
      getKnowledgeProblems(
        {
          ...filters,
          pageSize: 30,
        },
        signal,
      ),
  });
  const stats = useQuery({
    queryKey: ["operational-knowledge-stats"],
    queryFn: ({ signal }) => getKnowledgeCatalogStats(signal),
  });
  const companies = useQuery({
    queryKey: ["knowledge-companies"],
    queryFn: ({ signal }) => getKnowledgeCompanies(signal),
  });

  return (
    <div className="kb-page">
      <section className="kb-hero">
        <div>
          <span className="kb-eyebrow">RIGOR QUESTION BANK</span>
          <h1>Know exactly what you can practice here.</h1>
          <p>
            Search the source-backed interview catalog and distinguish fully runnable
            exercises from hosted prompts, questions in review, and approved external
            references. No metadata-only record is presented as executable.
          </p>
        </div>
        <Link className="kb-primary-action" href="/coding-lab">
          Open coding lab <Code2 size={16} />
        </Link>
      </section>

      <section className="kb-stat-strip" aria-label="Question-bank availability">
        <div>
          <CheckCircle2 size={17} />
          <strong>{(stats.data?.runnable_problems ?? 0).toLocaleString()}</strong>
          <span>runnable</span>
        </div>
        <div>
          <FileText size={17} />
          <strong>{(stats.data?.hosted_problems ?? 0).toLocaleString()}</strong>
          <span>hosted prompts</span>
        </div>
        <div>
          <Clock3 size={17} />
          <strong>{(stats.data?.in_review_problems ?? 0).toLocaleString()}</strong>
          <span>in review</span>
        </div>
        <div>
          <Building2 size={17} />
          <strong>{(stats.data?.reference_only_problems ?? 0).toLocaleString()}</strong>
          <span>reference only</span>
        </div>
      </section>

      <section className="kb-browser">
        <aside className="kb-filters">
          <div className="kb-filter-heading">
            <SlidersHorizontal size={16} />
            <strong>Refine practice</strong>
          </div>
          <label>
            <span>Availability</span>
            <select
              value={filters.availability}
              onChange={(event) => setFilter("availability", event.target.value)}
            >
              {availabilities.map(([value, label]) => (
                <option key={value || "all"} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </label>
          <label>
            <span>Difficulty</span>
            <select
              value={filters.difficulty}
              onChange={(event) => setFilter("difficulty", event.target.value)}
            >
              {difficulties.map((value) => (
                <option key={value || "all"} value={value}>
                  {value ? displayDifficulty(value) : "All difficulties"}
                </option>
              ))}
            </select>
          </label>
          <label>
            <span>Language</span>
            <select
              value={filters.language}
              onChange={(event) => setFilter("language", event.target.value)}
            >
              {languages.map((value) => (
                <option key={value || "all"} value={value}>
                  {value ? value.toUpperCase() : "All languages"}
                </option>
              ))}
            </select>
          </label>
          <label>
            <span>Company</span>
            <select
              value={filters.company}
              onChange={(event) => setFilter("company", event.target.value)}
            >
              <option value="">All companies</option>
              {(companies.data ?? []).slice(0, 100).map((company) => (
                <option key={company.id} value={company.slug}>
                  {company.name} · {company.problem_count}
                </option>
              ))}
            </select>
          </label>
          <label>
            <span>Sort</span>
            <select
              value={filters.sort}
              onChange={(event) => setFilter("sort", event.target.value)}
            >
              {sorts.map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </label>
          <button
            className="kb-clear-filters"
            onClick={() => router.replace(pathname)}
            type="button"
          >
            Clear all filters
          </button>
        </aside>

        <div className="kb-results">
          <div className="kb-toolbar">
            <label className="kb-search">
              <Search size={17} />
              <input
                aria-label="Search problems"
                placeholder="Search titles, IDs, topics, and companies"
                value={filters.query}
                onChange={(event) => setFilter("query", event.target.value)}
              />
            </label>
            <span>
              {problems.data
                ? `${problems.data.total.toLocaleString()} results`
                : "Loading…"}
            </span>
          </div>

          {problems.isError && (
            <div className="kb-message">
              <strong>The question bank could not be loaded.</strong>
              <button onClick={() => void problems.refetch()} type="button">
                Try again
              </button>
            </div>
          )}
          {problems.isLoading && (
            <div className="kb-skeleton-list" aria-label="Loading problem bank">
              {Array.from({ length: 8 }, (_, index) => (
                <div key={index} />
              ))}
            </div>
          )}
          {problems.data && problems.data.items.length === 0 && (
            <div className="kb-message">
              <strong>No problem matches these filters.</strong>
              <span>Clear one filter or broaden the search.</span>
            </div>
          )}
          {problems.data && problems.data.items.length > 0 && (
            <div className="kb-problem-table" role="table" aria-label="Problems">
              <div className="kb-problem-row kb-problem-row--header" role="row">
                <span>Status</span>
                <span>Problem</span>
                <span>Difficulty</span>
                <span>Languages</span>
                <span>Companies</span>
                <span />
              </div>
              {problems.data.items.map((problem) => (
                <Link
                  className="kb-problem-row"
                  href={`/problems/${problem.slug}`}
                  key={problem.id}
                  role="row"
                >
                  <span
                    className={`kb-availability kb-availability--${problem.availability}`}
                  >
                    {availabilityLabel(problem.availability)}
                  </span>
                  <span className="kb-problem-title">
                    <small>{problem.external_id ?? problem.canonical_key}</small>
                    <strong>{problem.title}</strong>
                    <i>
                      {problem.topics.slice(0, 3).map((topic) => (
                        <em key={topic}>{topic.replaceAll("-", " ")}</em>
                      ))}
                    </i>
                  </span>
                  <span
                    className={`kb-difficulty kb-difficulty--${problem.difficulty ?? "unrated"}`}
                  >
                    {displayDifficulty(problem.difficulty)}
                  </span>
                  <span className="kb-language-list">
                    {problem.languages.length
                      ? problem.languages.slice(0, 3).join(" · ").toUpperCase()
                      : "REFERENCE"}
                  </span>
                  <span>{problem.companies.slice(0, 2).join(" · ") || "—"}</span>
                  <span className="kb-row-actions" title={availabilityAction(problem.availability)}>
                    {problem.availability === "reference_only" ? (
                      <ExternalLink size={15} />
                    ) : (
                      <ArrowRight size={15} />
                    )}
                  </span>
                </Link>
              ))}
            </div>
          )}

          {problems.data && problems.data.total > problems.data.page_size && (
            <div className="kb-pagination">
              <button
                disabled={filters.page <= 1}
                onClick={() => setFilter("page", String(filters.page - 1))}
                type="button"
              >
                Previous
              </button>
              <span>
                Page {problems.data.page} of{" "}
                {Math.ceil(problems.data.total / problems.data.page_size)}
              </span>
              <button
                disabled={!problems.data.has_next}
                onClick={() => setFilter("page", String(filters.page + 1))}
                type="button"
              >
                Next
              </button>
            </div>
          )}
        </div>
      </section>
    </div>
  );
}
