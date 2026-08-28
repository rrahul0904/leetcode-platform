import type { CatalogQuestionPage } from "@/lib/api";
import { apiUrl, authMode, storedAccessToken } from "@/lib/auth";

export type QuestionNote = {
  id: string;
  question_slug: string;
  body: string;
  created_at: string;
  updated_at: string;
};

export type QuestionEngagement = {
  question_slug: string;
  bookmarked: boolean;
  notes: QuestionNote[];
};

export type BookmarkItem = {
  question_slug: string;
  title: string;
  created_at: string;
};

export type CandidateCatalogFilters = {
  query: string;
  track: string;
  skill: string;
  difficulty: string;
  role: string;
  companyStyle: string;
  completionStatus: string;
  sort: string;
  page?: number;
  pageSize?: number;
};

type RequestOptions = {
  method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
  body?: unknown;
  signal?: AbortSignal;
};

async function engagementRequest<T>(
  path: string,
  options: RequestOptions = {},
): Promise<T> {
  const token = authMode === "local" ? storedAccessToken() : null;
  const response = await fetch(`${apiUrl}${path}`, {
    method: options.method ?? "GET",
    headers: {
      Accept: "application/json",
      ...(options.body ? { "Content-Type": "application/json" } : {}),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    ...(options.body ? { body: JSON.stringify(options.body) } : {}),
    ...(options.signal ? { signal: options.signal } : {}),
    cache: "no-store",
  });

  if (!response.ok) {
    if (response.status === 401 && typeof window !== "undefined") {
      window.dispatchEvent(new Event("rigor:unauthorized"));
    }
    throw new Error(`SkillsForge API returned ${response.status}`);
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

function candidateCatalogParams(
  filters: CandidateCatalogFilters,
  bookmarked?: boolean,
) {
  const params = new URLSearchParams({
    page: String(filters.page ?? 1),
    page_size: String(filters.pageSize ?? 18),
    sort: filters.sort,
  });
  if (filters.query) params.set("query", filters.query);
  if (filters.track) params.set("track", filters.track);
  if (filters.skill) params.set("skill", filters.skill);
  if (filters.difficulty) params.set("difficulty", filters.difficulty);
  if (filters.role) params.set("role", filters.role);
  if (filters.companyStyle) params.set("company_style", filters.companyStyle);
  if (filters.completionStatus) {
    params.set("completion_status", filters.completionStatus);
  }
  if (bookmarked !== undefined) params.set("bookmarked", String(bookmarked));
  return params;
}

export function getCandidateQuestions(
  filters: CandidateCatalogFilters,
  signal?: AbortSignal,
  bookmarked?: boolean,
) {
  const params = candidateCatalogParams(filters, bookmarked);
  return engagementRequest<CatalogQuestionPage>(
    `/api/v1/candidate/questions?${params.toString()}`,
    signal ? { signal } : {},
  );
}

export function getQuestionEngagement(slug: string, signal?: AbortSignal) {
  return engagementRequest<QuestionEngagement>(
    `/api/v1/questions/${encodeURIComponent(slug)}/engagement`,
    signal ? { signal } : {},
  );
}

export function listCandidateBookmarks(signal?: AbortSignal) {
  return engagementRequest<BookmarkItem[]>(
    "/api/v1/candidate/bookmarks",
    signal ? { signal } : {},
  );
}

export function getBookmarkedQuestions(
  filters: CandidateCatalogFilters,
  signal?: AbortSignal,
) {
  return getCandidateQuestions(filters, signal, true);
}

export function bookmarkQuestion(slug: string) {
  return engagementRequest<QuestionEngagement>(
    `/api/v1/questions/${encodeURIComponent(slug)}/bookmark`,
    { method: "PUT" },
  );
}

export function removeQuestionBookmark(slug: string) {
  return engagementRequest<void>(
    `/api/v1/questions/${encodeURIComponent(slug)}/bookmark`,
    { method: "DELETE" },
  );
}

export function createQuestionNote(slug: string, body: string) {
  return engagementRequest<QuestionNote>(
    `/api/v1/questions/${encodeURIComponent(slug)}/notes`,
    { method: "POST", body: { body } },
  );
}

export function updateQuestionNote(slug: string, noteId: string, body: string) {
  return engagementRequest<QuestionNote>(
    `/api/v1/questions/${encodeURIComponent(slug)}/notes/${encodeURIComponent(noteId)}`,
    { method: "PATCH", body: { body } },
  );
}

export function deleteQuestionNote(slug: string, noteId: string) {
  return engagementRequest<void>(
    `/api/v1/questions/${encodeURIComponent(slug)}/notes/${encodeURIComponent(noteId)}`,
    { method: "DELETE" },
  );
}
