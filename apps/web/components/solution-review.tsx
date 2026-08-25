"use client";

import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, LockKeyhole, ShieldCheck } from "lucide-react";
import Link from "next/link";

import { ErrorState, LoadingState } from "@/components/page-ui";
import {
  getQuestionSolution,
  SolutionRevealError,
} from "@/lib/solution-api";

function renderValue(value: unknown) {
  if (value == null || value === "") return null;
  if (typeof value === "string") return <p>{value}</p>;
  return <pre>{JSON.stringify(value, null, 2)}</pre>;
}

export function SolutionReview({ slug }: { slug: string }) {
  const solution = useQuery({
    queryKey: ["question-solution", slug],
    queryFn: ({ signal }) => getQuestionSolution(slug, signal),
    retry: (count, error) =>
      !(error instanceof SolutionRevealError && error.status === 409) && count < 2,
  });

  if (solution.isLoading) {
    return (
      <div className="page-content">
        <LoadingState label="Loading solution review" />
      </div>
    );
  }
  if (
    solution.error instanceof SolutionRevealError &&
    solution.error.status === 409
  ) {
    return (
      <div className="page-content">
        <Link className="back-link" href={`/question-bank/${slug}`}>
          <ArrowLeft size={15} /> Back to question
        </Link>
        <section className="panel section-block">
          <LockKeyhole size={24} />
          <span className="eyebrow">SOLUTION LOCKED</span>
          <h1>Complete an attempt first</h1>
          <p>
            Runnable questions reveal the source-backed solution only after a
            completed submission or practice session. Hidden tests remain private.
          </p>
          <Link className="button button--primary" href={`/practice/${slug}`}>
            Start or resume practice
          </Link>
        </section>
      </div>
    );
  }
  if (solution.isError || !solution.data) {
    return (
      <div className="page-content">
        <ErrorState retry={() => void solution.refetch()} />
      </div>
    );
  }

  const item = solution.data;
  return (
    <div className="page-content">
      <Link className="back-link" href={`/question-bank/${slug}`}>
        <ArrowLeft size={15} /> Back to question
      </Link>
      <section className="detail-hero">
        <div>
          <span className="eyebrow">SOURCE-BACKED REVIEW</span>
          <h1>{item.title}</h1>
          <p>
            Review the reference answer after your attempt. This page never
            receives or displays hidden tests.
          </p>
        </div>
        <aside className="availability-card">
          <ShieldCheck size={22} />
          <span>HIDDEN TEST POLICY</span>
          <strong>Protected</strong>
          <p>Hidden tests revealed: {item.hidden_tests_revealed ? "yes" : "no"}</p>
        </aside>
      </section>
      <section className="panel section-block">
        <span className="eyebrow">REFERENCE SOLUTION</span>
        <pre className="starter-code">
          <code>{item.reference_solution}</code>
        </pre>
      </section>
      <section className="panel section-block">
        <span className="eyebrow">EXPLANATION</span>
        {renderValue(item.explanation)}
      </section>
      {item.expected_approach && (
        <section className="panel section-block">
          <span className="eyebrow">EXPECTED APPROACH</span>
          {renderValue(item.expected_approach)}
        </section>
      )}
      {(item.time_complexity || item.space_complexity) && (
        <section className="panel section-block">
          <span className="eyebrow">COMPLEXITY</span>
          {item.time_complexity && <p>Time: {item.time_complexity}</p>}
          {item.space_complexity && <p>Space: {item.space_complexity}</p>}
        </section>
      )}
      {item.trade_off_analysis && (
        <section className="panel section-block">
          <span className="eyebrow">TRADE-OFFS</span>
          {renderValue(item.trade_off_analysis)}
        </section>
      )}
      {item.common_mistakes && (
        <section className="panel section-block">
          <span className="eyebrow">COMMON MISTAKES</span>
          {renderValue(item.common_mistakes)}
        </section>
      )}
      {item.best_practices && (
        <section className="panel section-block">
          <span className="eyebrow">BEST PRACTICES</span>
          {renderValue(item.best_practices)}
        </section>
      )}
    </div>
  );
}
