import { Suspense } from "react";

import { LoadingState } from "@/components/page-ui";
import { QuestionBank } from "@/components/question-bank";

export default function QuestionBankPage() {
  return (
    <Suspense fallback={<LoadingState label="Loading question bank" />}>
      <QuestionBank />
    </Suspense>
  );
}
