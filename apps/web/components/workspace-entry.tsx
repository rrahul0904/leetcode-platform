"use client";

import { useQuery } from "@tanstack/react-query";
import { ArrowRight, SquareTerminal } from "lucide-react";
import Link from "next/link";

import { EmptyState, ErrorState, LoadingState, PageHeader } from "@/components/page-ui";
import { getPublishedQuestions } from "@/lib/api";

export function WorkspaceEntry() {
  const questions = useQuery({
    queryKey: ["published-questions", "workspace-entry"],
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
          sort: "relevance",
          pageSize: 1,
        },
        signal,
      ),
  });

  const question = questions.data?.items[0];

  return (
    <div className="page-content workspace-entry-page">
      <PageHeader
        eyebrow="PRACTICE WORKSPACE"
        title="Resume with context, not from scratch."
        description="Open a published exercise in the isolated workspace. Drafts, elapsed time, active executions, and deterministic results survive navigation and reconnects."
      />
      {questions.isLoading && (
        <LoadingState label="Selecting the next published exercise" />
      )}
      {questions.isError && (
        <ErrorState retry={() => void questions.refetch()} />
      )}
      {questions.data && !question && (
        <EmptyState
          title="No published workspace exercise is available."
          description="Choose external practice while the governed hosted catalog is being reviewed."
          action={
            <Link className="button button--ghost" href="/question-bank">
              Browse the question bank
            </Link>
          }
        />
      )}
      {question && (
        <section className="workspace-entry-card" aria-label="Recommended workspace">
          <div>
            <span>RECOMMENDED NEXT SESSION</span>
            <SquareTerminal size={34} />
          </div>
          <small>
            {question.external_id} · {question.difficulty} · {question.estimated_duration_minutes} MIN
          </small>
          <h2>{question.title}</h2>
          <p>
            {question.learning_objectives[0] ??
              "Open this governed exercise and build evidence through deterministic evaluation."}
          </p>
          <Link
            className="cinematic-button cinematic-button--primary"
            href={`/practice/${question.slug}`}
          >
            Open isolated workspace <ArrowRight size={16} />
          </Link>
        </section>
      )}
    </div>
  );
}
