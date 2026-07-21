"use client";

import { useQuery } from "@tanstack/react-query";
import {
  ChevronLeft,
  ChevronRight,
  Search,
  SlidersHorizontal,
} from "lucide-react";
import { useDeferredValue, useMemo, useState } from "react";

import {
  EmptyState,
  ErrorState,
  EvidenceNote,
  PageHeader,
} from "@/components/page-ui";
import { QuestionCard, QuestionCardSkeleton } from "@/components/question-card";
import { getPublishedQuestions } from "@/lib/api";
import { difficulties, tracks } from "@/lib/product-data";

const pageSize = 12;

export function QuestionBank() {
  const [query, setQuery] = useState("");
  const deferredQuery = useDeferredValue(query);
  const [track, setTrack] = useState("");
  const [difficulty, setDifficulty] = useState("");
  const [sort, setSort] = useState("relevance");
  const [page, setPage] = useState(1);
  const filters = useMemo(
    () => ({
      query: deferredQuery,
      track,
      skill: "",
      difficulty,
      role: "",
      companyStyle: "",
      completionStatus: "",
      sort,
      page,
      pageSize,
    }),
    [deferredQuery, track, difficulty, sort, page],
  );
  const questions = useQuery({
    queryKey: ["published-questions", filters],
    queryFn: ({ signal }) => getPublishedQuestions(filters, signal),
  });

  function updateFilter(update: () => void) {
    update();
    setPage(1);
  }
  function clearFilters() {
    setQuery("");
    setTrack("");
    setDifficulty("");
    setSort("relevance");
    setPage(1);
  }
  const totalPages = questions.data
    ? Math.max(1, Math.ceil(questions.data.total / pageSize))
    : 1;

  return (
    <div className="page-content">
      <PageHeader
        eyebrow="QUESTION BANK"
        title="Practice published, independently reviewed questions."
        description="Search the PostgreSQL-backed catalog. Only versions that completed automated validation, technical review, editorial review, and publication appear here."
      />
      <EvidenceNote>
        <strong>Candidate-safe publication boundary.</strong>
        <span>
          This catalog exposes public prompts and examples only. Hidden tests,
          reference solutions, private rubrics, and interviewer guidance stay
          server-side.
        </span>
      </EvidenceNote>
      <section className="catalog-toolbar" aria-label="Question filters">
        <label className="search-field">
          <Search size={18} />
          <span className="sr-only">Search question bank</span>
          <input
            value={query}
            onChange={(event) =>
              updateFilter(() => setQuery(event.target.value))
            }
            placeholder="Search skills, systems, or objectives"
          />
        </label>
        <label>
          <span className="sr-only">Track</span>
          <select
            value={track}
            onChange={(event) =>
              updateFilter(() => setTrack(event.target.value))
            }
          >
            {tracks.map(([value, label]) => (
              <option value={value} key={value}>
                {label}
              </option>
            ))}
          </select>
        </label>
        <label>
          <span className="sr-only">Difficulty</span>
          <select
            value={difficulty}
            onChange={(event) =>
              updateFilter(() => setDifficulty(event.target.value))
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
          <span className="sr-only">Sort</span>
          <select
            value={sort}
            onChange={(event) =>
              updateFilter(() => setSort(event.target.value))
            }
          >
            <option value="relevance">Relevance</option>
            <option value="title">Title</option>
            <option value="difficulty">Difficulty</option>
            <option value="duration">Duration</option>
            <option value="newest">Newest</option>
          </select>
        </label>
        <button
          className="button button--ghost button--icon"
          onClick={clearFilters}
        >
          <SlidersHorizontal size={16} /> Reset
        </button>
      </section>
      <div className="catalog-summary">
        <span>
          {questions.data
            ? `${questions.data.total.toLocaleString()} published questions`
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
          title="No published questions match these filters."
          description="Try broader filters. Authored drafts remain unavailable until independent review and publication are complete."
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
            onClick={() => setPage((value) => Math.max(1, value - 1))}
          >
            <ChevronLeft size={16} /> Previous
          </button>
          <span>
            {((page - 1) * pageSize + 1).toLocaleString()}–
            {Math.min(page * pageSize, questions.data.total).toLocaleString()}{" "}
            of {questions.data.total.toLocaleString()}
          </span>
          <button
            className="button button--dark"
            disabled={!questions.data.has_next}
            onClick={() => setPage((value) => value + 1)}
          >
            Next <ChevronRight size={16} />
          </button>
        </nav>
      )}
    </div>
  );
}
