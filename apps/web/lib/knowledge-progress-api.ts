const apiUrl = process.env.NEXT_PUBLIC_RIGOR_API_URL ?? "http://localhost:8002";

export type CandidateProblemState = {
  problem_id: string;
  slug: string;
  title: string;
  status: "viewed" | "attempted" | "solved" | "failed";
  bookmarked: boolean;
  revision_status: "none" | "marked" | "due" | "completed";
  private_notes: string;
  view_count: number;
  attempt_count: number;
  solved_count: number;
  failed_count: number;
  total_seconds: number;
  last_language: string | null;
  first_viewed_at: string | null;
  last_attempted_at: string | null;
  solved_at: string | null;
  last_activity_at: string;
};

export type CandidateProgressSummary = {
  viewed: number;
  attempted: number;
  solved: number;
  failed: number;
  bookmarked: number;
  revision_due: number;
  total_seconds: number;
  current_streak: number;
  longest_streak: number;
  languages: Record<string, number>;
};

export type CandidateProblemPatch = {
  bookmarked?: boolean;
  revision_status?: "none" | "marked" | "due" | "completed";
  private_notes?: string;
};

export type CandidateActivityInput = {
  event_type:
    | "problem_viewed"
    | "session_started"
    | "draft_saved"
    | "public_tests_run"
    | "submission_completed"
    | "problem_solved"
    | "problem_failed"
    | "session_time_recorded";
  language?: string | undefined;
  duration_seconds?: number;
  idempotency_key?: string;
  payload?: Record<string, unknown>;
};

function accessToken() {
  if (typeof window === "undefined" || typeof window.localStorage === "undefined") {
    return null;
  }
  return window.localStorage.getItem("rigor.auth.access-token");
}

async function request<T>(
  path: string,
  options: {
    method?: "GET" | "POST" | "PATCH";
    body?: unknown;
    signal?: AbortSignal;
  } = {},
): Promise<T> {
  const token = accessToken();
  const response = await fetch(`${apiUrl}${path}`, {
    method: options.method ?? "GET",
    headers: {
      Accept: "application/json",
      ...(options.body ? { "Content-Type": "application/json" } : {}),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    ...(options.body ? { body: JSON.stringify(options.body) } : {}),
    ...(options.signal ? { signal: options.signal } : {}),
  });
  if (!response.ok) {
    if (response.status === 401 && typeof window !== "undefined") {
      window.dispatchEvent(new Event("rigor:unauthorized"));
    }
    throw new Error(`Knowledge progress API returned ${response.status}`);
  }
  return (await response.json()) as T;
}

export function getCandidateProblemState(slug: string, signal?: AbortSignal) {
  return request<CandidateProblemState>(
    `/api/v1/knowledge/me/problems/${encodeURIComponent(slug)}`,
    signal ? { signal } : {},
  );
}

export function patchCandidateProblemState(
  slug: string,
  update: CandidateProblemPatch,
) {
  return request<CandidateProblemState>(
    `/api/v1/knowledge/me/problems/${encodeURIComponent(slug)}`,
    { method: "PATCH", body: update },
  );
}

export function recordCandidateProblemActivity(
  slug: string,
  activity: CandidateActivityInput,
) {
  return request<CandidateProblemState>(
    `/api/v1/knowledge/me/problems/${encodeURIComponent(slug)}/events`,
    { method: "POST", body: activity },
  );
}

export function getCandidateProgressSummary(signal?: AbortSignal) {
  return request<CandidateProgressSummary>(
    "/api/v1/knowledge/me/summary",
    signal ? { signal } : {},
  );
}

export function getCandidateBookmarks(signal?: AbortSignal) {
  return request<CandidateProblemState[]>(
    "/api/v1/knowledge/me/bookmarks",
    signal ? { signal } : {},
  );
}
