import { Suspense } from "react";

import { OperationalQuestionBank } from "@/components/operational-question-bank";

export default function ProblemsPage() {
  return (
    <Suspense fallback={<div className="kb-workspace-loading">Loading question bank…</div>}>
      <OperationalQuestionBank />
    </Suspense>
  );
}
