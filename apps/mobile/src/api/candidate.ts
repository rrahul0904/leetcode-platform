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
  ExecutionResult,
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

export function getPrincipal(signal?: AbortSignal) {
  return apiClient.request<AuthenticatedPrincipal>("/api/v1/auth/me", { signal });
}

export function getProfile(signal?: AbortSignal) {
  return apiClient.request<CandidateProfile>("/api/v1/profile", { signal });
}

export function putProfile(profile: CandidateProfileInput) {
  return apiClient.request<CandidateProfile>("/api/v1/profile", {
    method: "PUT",
    body: profile,
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
    body: { question_slug: questionSlug, runtime: "python3.13" },
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
      body: { draft_code: draftCode, elapsed_seconds: elapsedSeconds },
    },
  );
}

export function runPracticeCode(slug: string, sessionId: string, sourceCode: string) {
  return apiClient.request<ExecutionResult>(
    `/api/v1/questions/${encodeURIComponent(slug)}/run`,
    {
      method: "POST",
      body: { session_id: sessionId, source_code: sourceCode },
    },
  );
}

export function submitPracticeCode(
  slug: string,
  sessionId: string,
  sourceCode: string,
  idempotencyKey: string,
) {
  return apiClient.request<CandidateSubmission>(
    `/api/v1/questions/${encodeURIComponent(slug)}/submissions`,
    {
      method: "POST",
      idempotencyKey,
      body: {
        session_id: sessionId,
        source_code: sourceCode,
        runtime: "python3.13",
      },
    },
  );
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
