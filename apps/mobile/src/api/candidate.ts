import { apiClient } from "./client";
import type {
  AuthenticatedPrincipal,
  CandidateProfile,
  CandidateProfileInput,
  CandidateQuestionDetail,
  CandidateReadiness,
  CandidateSubmission,
  CatalogQuestionPage,
  CompetencyReadiness,
  ExecutionAccepted,
  ExecutionResult,
  ExecutionView,
  NextAction,
  PracticeHint,
  PracticeSession,
} from "./types";

export interface QuestionFilters {
  query?: string;
  track?: string;
  skill?: string;
  difficulty?: string;
  role?: string;
  companyStyle?: string;
  completionStatus?: string;
  sort?: string;
  page?: number;
  pageSize?: number;
}

const TERMINAL_EXECUTION_STATUSES = new Set<ExecutionView["status"]>([
  "COMPLETED",
  "FAILED",
  "TIMEOUT",
  "CANCELLED",
]);

function jsonBody(value: unknown): string {
  return JSON.stringify(value);
}

function sleep(milliseconds: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, milliseconds));
}

function fallbackIdempotencyKey(prefix: string): string {
  return `${prefix}-${Date.now()}-${Math.random().toString(36).slice(2, 12)}`;
}

function legacyExecutionState(execution: ExecutionView): ExecutionResult["state"] {
  if (execution.status === "QUEUED" || execution.status === "DISPATCHING") {
    return "QUEUED";
  }
  if (execution.status === "RUNNING") return "RUNNING";
  if (execution.status === "CANCELLED") return "CANCELLED";
  if (execution.status === "TIMEOUT") return "TIMED_OUT";
  if (execution.status === "FAILED") return "ERROR";
  if (!execution.result) return "ERROR";

  const publicPassed = execution.result.public_results.every((test) => test.passed);
  const hiddenPassed = execution.result.hidden_passed === execution.result.hidden_total;
  return publicPassed && hiddenPassed ? "PASSED" : "FAILED";
}

function toLegacyExecutionResult(execution: ExecutionView): ExecutionResult {
  const result = execution.result;
  return {
    execution_request_id: execution.execution_id,
    submission_id: execution.submission_id,
    state: legacyExecutionState(execution),
    public_results: (result?.public_results ?? []).map((test) => ({
      test_id: test.test_id,
      name: test.name,
      passed: test.passed,
      expected: test.expected ?? null,
      actual: test.actual ?? null,
      duration_ms: null,
    })),
    hidden_total: result?.hidden_total ?? 0,
    hidden_passed: result?.hidden_passed ?? 0,
    runtime_ms: execution.runtime_ms,
    memory_kb:
      execution.memory_peak_bytes === null
        ? null
        : Math.ceil(execution.memory_peak_bytes / 1024),
    error_category: execution.error,
    candidate_message: result?.candidate_message ?? execution.error,
    quality_signals: {
      durable_execution_status: execution.status,
      durable_execution_attempt: execution.attempt,
    },
  };
}

export function getPrincipal(signal?: AbortSignal) {
  return apiClient.request<AuthenticatedPrincipal>("/api/v1/auth/me", { signal });
}

export function getProfile(signal?: AbortSignal) {
  return apiClient.request<CandidateProfile>("/api/v1/profile", { signal });
}

export function putProfile(profile: CandidateProfileInput) {
  return apiClient.request<CandidateProfile>("/api/v1/profile", {
    method: "PUT",
    body: jsonBody(profile),
  });
}

export function getReadiness(signal?: AbortSignal) {
  return apiClient.request<CandidateReadiness>("/api/v1/me/readiness", { signal });
}

export function getCompetencies(signal?: AbortSignal) {
  return apiClient.request<CompetencyReadiness[]>("/api/v1/me/competencies", {
    signal,
  });
}

export function getNextAction(signal?: AbortSignal) {
  return apiClient.request<NextAction>("/api/v1/me/next-action", { signal });
}

export function getQuestions(filters: QuestionFilters = {}, signal?: AbortSignal) {
  const params = new URLSearchParams({
    page: String(filters.page ?? 1),
    page_size: String(filters.pageSize ?? 24),
    sort: filters.sort ?? "relevance",
  });
  if (filters.query) params.set("query", filters.query);
  if (filters.track) params.set("track", filters.track);
  if (filters.skill) params.set("skill", filters.skill);
  if (filters.difficulty) params.set("difficulty", filters.difficulty);
  if (filters.role) params.set("role", filters.role);
  if (filters.companyStyle) params.set("company_style", filters.companyStyle);
  if (filters.completionStatus) params.set("completion_status", filters.completionStatus);
  return apiClient.request<CatalogQuestionPage>(`/api/v1/questions?${params.toString()}`, {
    signal,
  });
}

export function getQuestion(slug: string, signal?: AbortSignal) {
  return apiClient.request<CandidateQuestionDetail>(
    `/api/v1/questions/${encodeURIComponent(slug)}`,
    { signal },
  );
}

export function getPracticeSessions(signal?: AbortSignal) {
  return apiClient.request<PracticeSession[]>("/api/v1/practice-sessions", { signal });
}

export function createPracticeSession(questionSlug: string) {
  return apiClient.request<PracticeSession>("/api/v1/practice-sessions", {
    method: "POST",
    body: jsonBody({ question_slug: questionSlug, runtime: "python3.13" }),
  });
}

export function getPracticeSession(sessionId: string, signal?: AbortSignal) {
  return apiClient.request<PracticeSession>(
    `/api/v1/practice-sessions/${encodeURIComponent(sessionId)}`,
    { signal },
  );
}

export function savePracticeDraft(
  sessionId: string,
  draftCode: string,
  elapsedSeconds: number,
) {
  return apiClient.request<PracticeSession>(
    `/api/v1/practice-sessions/${encodeURIComponent(sessionId)}`,
    {
      method: "PATCH",
      body: jsonBody({ draft_code: draftCode, elapsed_seconds: elapsedSeconds }),
    },
  );
}

async function queueRun(
  slug: string,
  sessionId: string,
  sourceCode: string,
  idempotencyKey: string,
): Promise<ExecutionAccepted> {
  return apiClient.request<ExecutionAccepted>(
    `/api/v1/questions/${encodeURIComponent(slug)}/run`,
    {
      method: "POST",
      headers: { "Idempotency-Key": idempotencyKey },
      body: jsonBody({ session_id: sessionId, source_code: sourceCode }),
    },
  );
}

async function queueSubmission(
  slug: string,
  sessionId: string,
  sourceCode: string,
  idempotencyKey: string,
): Promise<ExecutionAccepted> {
  return apiClient.request<ExecutionAccepted>(
    `/api/v1/questions/${encodeURIComponent(slug)}/submissions`,
    {
      method: "POST",
      headers: { "Idempotency-Key": idempotencyKey },
      body: jsonBody({
        session_id: sessionId,
        source_code: sourceCode,
        runtime: "python3.13",
      }),
    },
  );
}

export function getExecution(executionId: string, signal?: AbortSignal) {
  return apiClient.request<ExecutionView>(
    `/api/v1/executions/${encodeURIComponent(executionId)}`,
    { signal },
  );
}

export async function waitForExecution(
  executionId: string,
  options: { maxAttempts?: number; pollIntervalMs?: number } = {},
): Promise<ExecutionView> {
  const maxAttempts = options.maxAttempts ?? 120;
  const pollIntervalMs = options.pollIntervalMs ?? 500;
  for (let attempt = 0; attempt < maxAttempts; attempt += 1) {
    const execution = await getExecution(executionId);
    if (TERMINAL_EXECUTION_STATUSES.has(execution.status)) {
      return execution;
    }
    await sleep(pollIntervalMs);
  }
  throw new Error("Execution status did not reach a terminal state in time.");
}

export async function runPracticeCode(
  slug: string,
  sessionId: string,
  sourceCode: string,
  idempotencyKey = fallbackIdempotencyKey("mobile-run"),
): Promise<ExecutionResult> {
  const accepted = await queueRun(slug, sessionId, sourceCode, idempotencyKey);
  return toLegacyExecutionResult(await waitForExecution(accepted.execution_id));
}

export function getSubmission(submissionId: string, signal?: AbortSignal) {
  return apiClient.request<CandidateSubmission>(
    `/api/v1/submissions/${encodeURIComponent(submissionId)}`,
    { signal },
  );
}

export async function waitForSubmission(
  submissionId: string,
  options: { maxAttempts?: number; pollIntervalMs?: number } = {},
): Promise<CandidateSubmission> {
  const maxAttempts = options.maxAttempts ?? 10;
  const pollIntervalMs = options.pollIntervalMs ?? 250;
  let lastError: unknown;
  for (let attempt = 0; attempt < maxAttempts; attempt += 1) {
    try {
      return await getSubmission(submissionId);
    } catch (error) {
      lastError = error;
      await sleep(pollIntervalMs);
    }
  }
  throw lastError instanceof Error
    ? lastError
    : new Error("Submission finalization was not observable in time.");
}

export async function submitPracticeCode(
  slug: string,
  sessionId: string,
  sourceCode: string,
  idempotencyKey: string,
): Promise<CandidateSubmission> {
  const accepted = await queueSubmission(slug, sessionId, sourceCode, idempotencyKey);
  const execution = await waitForExecution(accepted.execution_id);
  const submissionId = execution.submission_id ?? accepted.submission_id;
  if (!submissionId) {
    throw new Error("Durable submission completed without a submission identifier.");
  }
  return waitForSubmission(submissionId);
}

export function revealHint(sessionId: string) {
  return apiClient.request<PracticeHint>(
    `/api/v1/practice-sessions/${encodeURIComponent(sessionId)}/hints`,
    { method: "POST" },
  );
}

export function getSubmissions(signal?: AbortSignal) {
  return apiClient.request<CandidateSubmission[]>("/api/v1/submissions", { signal });
}
