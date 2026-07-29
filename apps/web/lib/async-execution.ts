import type { CandidateSubmission } from "@/lib/api";

const apiUrl = process.env.NEXT_PUBLIC_RIGOR_API_URL ?? "http://localhost:8002";

export type AsyncExecutionStatus =
  | "QUEUED"
  | "DISPATCHING"
  | "RUNNING"
  | "COMPLETED"
  | "FAILED"
  | "TIMEOUT"
  | "CANCELLED";

export type AsyncPublicTestResult = {
  test_id: string;
  name: string;
  passed: boolean;
  expected: unknown;
  actual: unknown;
  error_category: string | null;
};

export type AsyncExecutionResult = {
  public_results: AsyncPublicTestResult[];
  hidden_total: number;
  hidden_passed: number;
  stdout: string;
  stderr: string;
  candidate_message: string | null;
};

export type ExecutionAccepted = {
  execution_id: string;
  submission_id: string | null;
  status: AsyncExecutionStatus;
  duplicate: boolean;
};

export type AsyncExecutionView = {
  execution_id: string;
  submission_id: string | null;
  status: AsyncExecutionStatus;
  execution_type: "RUN" | "SUBMIT";
  runtime: string;
  created_at: string;
  queued_at: string;
  dispatch_started_at: string | null;
  running_at: string | null;
  completed_at: string | null;
  runtime_ms: number | null;
  error_category: string | null;
  result: AsyncExecutionResult | null;
};

const terminalStates = new Set<AsyncExecutionStatus>([
  "COMPLETED",
  "FAILED",
  "TIMEOUT",
  "CANCELLED",
]);

export function isTerminalExecution(status: AsyncExecutionStatus) {
  return terminalStates.has(status);
}

async function executionRequest<T>(
  path: string,
  options: {
    method?: string;
    body?: unknown;
    headers?: Record<string, string>;
    signal?: AbortSignal;
  } = {},
): Promise<T> {
  const accessToken =
    typeof window === "undefined" || typeof window.localStorage === "undefined"
      ? null
      : window.localStorage.getItem("rigor.auth.access-token");
  const response = await fetch(`${apiUrl}${path}`, {
    method: options.method ?? "GET",
    headers: {
      Accept: "application/json",
      ...(options.body ? { "Content-Type": "application/json" } : {}),
      ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
      ...options.headers,
    },
    ...(options.body ? { body: JSON.stringify(options.body) } : {}),
    ...(options.signal ? { signal: options.signal } : {}),
  });
  if (!response.ok) {
    if (response.status === 401 && typeof window !== "undefined") {
      window.dispatchEvent(new Event("rigor:unauthorized"));
    }
    throw new Error(`Rigor execution API returned ${response.status}`);
  }
  return (await response.json()) as T;
}

export function queueRunExecution(
  slug: string,
  sessionId: string,
  sourceCode: string,
  idempotencyKey: string,
) {
  return executionRequest<ExecutionAccepted>(
    `/api/v1/questions/${encodeURIComponent(slug)}/run`,
    {
      method: "POST",
      headers: { "Idempotency-Key": idempotencyKey },
      body: { session_id: sessionId, source_code: sourceCode },
    },
  );
}

export function queueSubmitExecution(
  slug: string,
  sessionId: string,
  sourceCode: string,
  idempotencyKey: string,
) {
  return executionRequest<ExecutionAccepted>(
    `/api/v1/questions/${encodeURIComponent(slug)}/submissions`,
    {
      method: "POST",
      headers: { "Idempotency-Key": idempotencyKey },
      body: {
        session_id: sessionId,
        source_code: sourceCode,
        runtime: "python3.13",
      },
    },
  );
}

export function getExecution(executionId: string, signal?: AbortSignal) {
  return executionRequest<AsyncExecutionView>(
    `/api/v1/executions/${encodeURIComponent(executionId)}`,
    signal ? { signal } : {},
  );
}

export function cancelExecution(executionId: string) {
  return executionRequest<AsyncExecutionView>(
    `/api/v1/executions/${encodeURIComponent(executionId)}/cancel`,
    { method: "POST" },
  );
}

export function getCompletedSubmission(submissionId: string, signal?: AbortSignal) {
  return executionRequest<CandidateSubmission>(
    `/api/v1/submissions/${encodeURIComponent(submissionId)}`,
    signal ? { signal } : {},
  );
}
