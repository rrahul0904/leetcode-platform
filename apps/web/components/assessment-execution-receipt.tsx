import type { CandidateCodeExecution } from "@/lib/employer-assessment-api";

type Props = {
  mode: "RUN" | "SUBMIT";
  receipt: CandidateCodeExecution;
};

const states = {
  queued: "Waiting for isolated runner",
  dispatching: "Allocating sandbox",
  running: "Running in isolated sandbox",
  completed: "Execution completed",
  failed: "Execution failed",
  timeout: "Execution timed out",
} as const;

/** Reads real trusted API receipts. Never renders confidential fixture inputs/expected values. */
export function AssessmentExecutionReceipt({ mode, receipt }: Props) {
  const terminal = ["completed", "failed", "timeout"].includes(receipt.status);
  const passed = receipt.public_results?.filter((item) => item.passed).length ?? 0;
  const total = receipt.public_results?.length ?? 0;
  const success = receipt.status === "completed";
  return (
    <section aria-label={mode === "RUN" ? "Sample execution result" : "Final code grading result"}
      className="mt-4 overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
      <header className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 bg-slate-50 px-4 py-3">
        <div className="flex items-center gap-3">
          <span aria-hidden="true" className={
            "h-2.5 w-2.5 rounded-full " +
            (!terminal ? "animate-pulse bg-sky-500"
              : success ? "bg-emerald-500" : "bg-amber-500")
          } />
          <div>
            <p className="text-sm font-semibold text-slate-900">
              {mode === "RUN" ? "Sample test execution" : "Final grading receipt"}
            </p>
            <p className="text-xs text-slate-600">{states[receipt.status]}</p>
          </div>
        </div>
        <span className="font-mono text-xs text-slate-500">
          {receipt.runtime_ms !== null ? receipt.runtime_ms + " ms" : "Queued"}
        </span>
      </header>
      <div className="space-y-3 p-4">
        {!terminal && (
          <p role="status" className="text-sm text-slate-600">
            The server is processing this request. Results update automatically.
            Candidate code never executes in this browser.
          </p>
        )}
        {total > 0 && (
          <div className="rounded-lg bg-slate-50 p-3">
            <p className="text-sm font-semibold text-slate-900">
              {passed} of {total} public sample tests passed
            </p>
            <ul className="mt-2 space-y-1">
              {receipt.public_results?.map((test) => (
                <li key={test.test_id} className="flex items-center justify-between gap-3 text-sm">
                  <span className="truncate text-slate-700">{test.name}</span>
                  <span className={test.passed ? "text-emerald-700" : "text-rose-700"}>
                    {test.passed ? "Passed" : "Failed"}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        )}
        {mode === "SUBMIT" && receipt.status === "completed" && (
          <div className="flex flex-wrap justify-between gap-3 rounded-lg border border-sky-100 bg-sky-50 p-3">
            <div>
              <p className="text-xs font-semibold uppercase tracking-wide text-sky-800">Private test summary</p>
              <p className="text-sm text-sky-950">
                {receipt.hidden_passed ?? 0} / {receipt.hidden_total ?? 0} passed
              </p>
            </div>
            {receipt.awarded_marks !== null && (
              <div className="text-right">
                <p className="text-xs text-sky-800">Automated points</p>
                <p className="text-xl font-bold text-sky-950">{receipt.awarded_marks}</p>
              </div>
            )}
          </div>
        )}
        {receipt.error_category && (
          <p role="status" className="text-xs text-amber-800">
            Execution diagnostic: {receipt.error_category.replaceAll("_", " ")}
          </p>
        )}
        <p className="break-all font-mono text-[11px] text-slate-400">
          Receipt {receipt.id}
        </p>
      </div>
    </section>
  );
}
