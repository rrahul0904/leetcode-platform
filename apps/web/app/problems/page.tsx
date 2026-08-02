import { Suspense } from "react";

import { KnowledgeProblemBank } from "@/components/knowledge-problem-bank";

export default function ProblemsPage() {
  return (
    <Suspense fallback={<div className="kb-workspace-loading">Loading question bank…</div>}>
      <KnowledgeProblemBank />
    </Suspense>
  );
}
