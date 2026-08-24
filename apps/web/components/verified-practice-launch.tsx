"use client";

import { useQuery } from "@tanstack/react-query";
import { ArrowRight, LockKeyhole, Play } from "lucide-react";
import Link from "next/link";

import { getKnowledgeProblem, type ProblemDetail } from "@/lib/knowledge-api";

export function practiceHrefForProblem(problem: ProblemDetail | undefined) {
  if (
    !problem ||
    problem.availability !== "runnable" ||
    !problem.practice_question_slug ||
    !problem.practice_runtime
  ) {
    return null;
  }
  return `/practice/${encodeURIComponent(problem.practice_question_slug)}`;
}

export function VerifiedPracticeLaunch({ slug }: { slug: string }) {
  const problem = useQuery({
    queryKey: ["knowledge-problem", slug],
    queryFn: ({ signal }) => getKnowledgeProblem(slug, signal),
  });
  const href = practiceHrefForProblem(problem.data);

  if (problem.isLoading) {
    return (
      <aside className="kb-runtime-bridge" aria-live="polite">
        <span>VERIFYING RUNTIME PACKAGE</span>
      </aside>
    );
  }

  if (!problem.data || problem.isError) return null;

  if (!href) {
    return (
      <aside className="kb-runtime-bridge kb-runtime-bridge--locked">
        <LockKeyhole size={17} />
        <div>
          <strong>Reference / reading mode</strong>
          <span>
            This record has no verified current runtime package. Run and Submit stay disabled.
          </span>
        </div>
      </aside>
    );
  }

  return (
    <aside className="kb-runtime-bridge kb-runtime-bridge--ready">
      <Play size={17} />
      <div>
        <strong>Verified {problem.data.practice_runtime} judge package</strong>
        <span>
          Open the existing isolated practice workspace for durable Run, Submit,
          hidden validation, cancellation, and refresh recovery.
        </span>
      </div>
      <Link href={href}>
        Open practice <ArrowRight size={15} />
      </Link>
    </aside>
  );
}
