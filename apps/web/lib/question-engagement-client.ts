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
