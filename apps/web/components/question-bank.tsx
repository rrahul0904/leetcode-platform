"use client";

import { useQuery } from "@tanstack/react-query";
import {
  Bookmark,
  ChevronLeft,
  ChevronRight,
  Search,
  SlidersHorizontal,
} from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useDeferredValue, useMemo } from "react";

import { ExternalCatalog } from "@/components/external-practice";
import {
  EmptyState,
  ErrorState,
  EvidenceNote,
  PageHeader,
} from "@/components/page-ui";
import { QuestionCard, QuestionCardSkeleton } from "@/components/question-card";
import { getPublishedQuestions } from "@/lib/api";
import { difficulties, tracks } from "@/lib/product-data";
import { getBookmarkedQuestions } from "@/lib/question-engagement-client";

const pageSize = 12;
type CatalogMode = "all" | "hosted" | "external";

function catalogMode(value: string | null): CatalogMode {
  return value === "hosted" || value === "external" ? value : "all";
}

function pageNumber(value: string | null) {
  const parsed = Number(value ?? "1");
  return Number.isInteger(parsed) && parsed > 0 ? parsed : 1;
}

export function QuestionBank() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  const mode = catalogMode(searchParams.get("mode"));
  const query = searchParams.get("q") ?? "";
  const deferredQuery = useDeferredValue(query);
  const track = searchParams.get("track") ?? "";
  const skill = searchParams.get("skill") ?? "";
  const difficulty = searchParams.get("difficulty") ?? "";
  const completionStatus = searchParams.get("completion") ?? "";
  const sort = searchParams.get("sort") ?? "relevance";
  const bookmarkedOnly = searchParams.get("bookmarked") === "true";
  const page = pageNumber(searchParams.get("page"));

  function replaceParams(
    updates: Record<string, string | null>,
    options: { resetPage?: boolean } = { resetPage: true },
  ) {
    const next = new URLSearchParams(searchParams.toString());
    for (const [key, value] of Object.entries(updates)) {
      if (!value) next.delete(key);
      else next.set(key, value);
    }
    if (options.resetPage !== false) next.delete("page");
    const suffix = next.toString();
    router.replace(suffix ? `${pathname}?${suffix}` : pathname, { scroll: false });
  }

  const filters = useMemo(
    () => ({
      query: deferredQuery,
      track,
      skill,
      difficulty,
      role: "",
      companyStyle: "",
      completionStatus,
      sort,
      page,
      pageSize,
    }),
    [deferredQuery, track, skill, difficulty, completionStatus, sort, page],
  );

  const questions = useQuery({
    queryKey: ["published-questions", bookmarkedOnly ? "bookmarked" : "all", filters],
    queryFn: ({ signal }) =>
      bookmarkedOnly
        ? getBookmarkedQuestions(filters, signal)
        : getPublishedQuestions(filters, signal),
    enabled: mode !== "external",
  });

  function clearFilters() {
    replaceParams({
      q: null,
      track: null,
      skill: null,
      difficulty: null,
      completion: null,
      sort: null,
      bookmarked: null,
      page: null,
    });
  }

  const totalPages = questions.data
    ? Math.max(1, Math.ceil(questions.data.total / pageSize))
    : 1;
  const showExternal = mode !== "hosted" && !bookmarkedOnly;

  return (
    <div className="page-content">
      <PageHeader
        eyebrow="QUESTION BANK"
        title="Choose work that changes your readiness."
        description="Published SkillsForge AI questions are backed by the candidate catalog. Filters remain in the URL so the same view survives refresh and can be shared."
      />
      <div className="catalog-tabs" role="tablist" aria-label="Practice type">
        {(
          [
            ["all", "All practice"],
            ["hosted", "Hosted questions"],
            ["external", "External practice"],
          ] as const
        ).map(([value, label]) => (
          <button
            key={value}
            type="button"
            role="tab"
            aria-selected={mode === value}
            className={
              mode === value ? "catalog-tab catalog-tab--active" : "catalog-tab"
            }
            onClick={() =>
              replaceParams({ mode: value === "all" ? null : value })
            }
          >
            {label}
          </button>
        ))}
        <Link className="catalog-tab" href="/mock-interviews" role="tab">
          Mock Interviews
        </Link>
        <Link className="catalog-tab" href="/learning-paths" role="tab">
          Lessons
        </Link>
      </div>
      {mode !== "external" && (
        <>
          <EvidenceNote>
            <strong>Candidate-safe publication boundary.</strong>
            <span>
              Hosted cards expose public prompts, examples, constraints, and starter
              source only. Hidden tests, solutions, rubrics, and interviewer guidance
              stay server-side.
            </span>
          </EvidenceNote>
          {mode === "all" && (
            <h2 className="catalog-section-title">
              {bookmarkedOnly ? "Bookmarked questions" : "Hosted questions"}
            </h2>
          )}
          <section className="catalog-toolbar" aria-label="Question filters">
            <label className="search-field">
              <Search size={18} />
              <span className="sr-only">Search question bank</span>
              <input
                value={query}
                onChange={(event) => replaceParams({ q: event.target.value })}
                placeholder="Search skills, systems, or objectives"
              />
            </label>
            <label>
              <span className="sr-only">Track</span>
              <select
                value={track}
                onChange={(event) => replaceParams({ track: event.target.value })}
              >
                {tracks.map(([value, label]) => (
                  <option value={value} key={value}>
                    {label}
                  </option>
                ))}
              </select>
            </label>
            <label>
              <span className="sr-only">Skill</span>
              <input
                value={skill}
                onChange={(event) => replaceParams({ skill: event.target.value })}
                placeholder="Skill slug"
              />
            </label>
            <label>
              <span className="sr-only">Difficulty</span>
              <select
                value={difficulty}
                onChange={(event) =>
                  replaceParams({ difficulty: event.target.value })
                }
              >
                {difficulties.map((value) => (
                  <option value={value} key={value}>
                    {value || "All levels"}
                  </option>
                ))}
              </select>
            </label>
            <label>
              <span className="sr-only">Completion status</span>
              <select
                value={completionStatus}
                onChange={(event) =>
                  replaceParams({ completion: event.target.value })
                }
              >
                <option value="">Any completion state</option>
                <option value="not_started">Not started</option>
              </select>
            </label>
            <label>
              <span className="sr-only">Sort</span>
              <select
                value={sort}
                onChange={(event) => replaceParams({ sort: event.target.value })}
              >
                <option value="relevance">Relevance</option>
                <option value="title">Title</option>
                <option value="difficulty">Difficulty</option>
                <option value="duration">Duration</option>
                <option value="newest">Newest</option>
              </select>
            </label>
            <label className="status-chip">
              <input
                type="checkbox"
                checked={bookmarkedOnly}
                onChange={(event) =>
                  replaceParams({
                    bookmarked: event.target.checked ? "true" : null,
                    mode: event.target.checked && mode === "external" ? "hosted" : null,
                  })
                }
              />
              <Bookmark size={14} /> Bookmarked only
            </label>
            <button
              className="button button--ghost button--icon"
              type="button"
              onClick={clearFilters}
            >
              <SlidersHorizontal size={16} /> Reset
            </button>
          </section>
          <div className="catalog-summary">
            <span>
              {questions.data
                ? `${questions.data.total.toLocaleString()} ${
                    bookmarkedOnly ? "bookmarked" : "published"
                  } questions`
                : "Reading catalog…"}
            </span>
            <span>
              Page {page} of {totalPages}
            </span>
          </div>
          {questions.isError && (
            <ErrorState retry={() => void questions.refetch()} />
          )}
          {questions.isLoading && (
            <div className="question-grid">
              {Array.from({ length: pageSize }, (_, index) => (
                <QuestionCardSkeleton key={index} />
              ))}
            </div>
          )}
          {questions.data?.items.length === 0 && (
            <EmptyState
              title={
                bookmarkedOnly
                  ? "No bookmarked questions match these filters."
                  : "No published questions match these filters."
              }
              description={
                bookmarkedOnly
                  ? "Bookmark a published question or broaden the current filters."
                  : "Try broader filters. Authored drafts remain unavailable until independent review and publication are complete."
              }
              action={
                <button className="button button--dark" onClick={clearFilters}>
                  Clear filters
                </button>
              }
            />
          )}
          {questions.data && questions.data.items.length > 0 && (
            <div className="question-grid">
              {questions.data.items.map((question) => (
                <QuestionCard question={question} key={question.slug} />
              ))}
            </div>
          )}
          {questions.data && questions.data.total > pageSize && (
            <nav className="pagination" aria-label="Catalog pages">
              <button
                className="button button--ghost"
                disabled={page === 1}
                onClick={() =>
                  replaceParams(
                    { page: String(Math.max(1, page - 1)) },
                    { resetPage: false },
                  )
                }
              >
                <ChevronLeft size={16} /> Previous
              </button>
              <span>
                {((page - 1) * pageSize + 1).toLocaleString()}–
                {Math.min(page * pageSize, questions.data.total).toLocaleString()} of{" "}
                {questions.data.total.toLocaleString()}
              </span>
              <button
                className="button button--dark"
                disabled={!questions.data.has_next}
                onClick={() =>
                  replaceParams(
                    { page: String(page + 1) },
                    { resetPage: false },
                  )
                }
              >
                Next <ChevronRight size={16} />
              </button>
            </nav>
          )}
        </>
      )}
      {showExternal && (
        <section className={mode === "all" ? "section-block" : undefined}>
          {mode === "all" && (
            <h2 className="catalog-section-title">External practice</h2>
          )}
          <ExternalCatalog pageSize={12} />
        </section>
      )}
    </div>
  );
}
