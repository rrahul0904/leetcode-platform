const apiUrl = process.env.NEXT_PUBLIC_RIGOR_API_URL ?? "/api/backend";
const authMode = process.env.NEXT_PUBLIC_RIGOR_AUTH_MODE ?? "clerk";

export type MockInterviewTemplate = {
  slug: string;
  label: string;
  description: string;
  competencies: string[];
  phases: Array<{ slug: string; label: string }>;
};

export type MockInterviewMessage = {
  id: string;
  session_id: string;
  sequence_number: number;
  role: string;
  phase: string;
  content: string;
  evidence: Record<string, unknown>;
  created_at: string;
};

export type MockInterviewReport = {
  overall_score: number;
  rubric_evidence: Array<Record<string, unknown>>;
  strengths: string[];
  growth_areas: string[];
  next_steps: string[];
};

export type MockInterviewSessionSummary = {
  id: string;
  interview_type: string;
  target_role: string;
  focus: string;
  focus_label: string;
  status: "IN_PROGRESS" | "PAUSED" | "COMPLETED" | "CANCELLED";
  current_phase: string;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
  updated_at: string;
};

export type MockInterviewSession = MockInterviewSessionSummary & {
  messages: MockInterviewMessage[];
  report: MockInterviewReport | null;
};

function localAccessToken() {
  if (
    authMode !== "local" ||
    typeof window === "undefined" ||
    typeof window.localStorage === "undefined"
  ) {
    return null;
  }
  return window.localStorage.getItem("rigor.auth.access-token");
}

async function request<T>(
  path: string,
  options: {
    method?: string;
    body?: unknown;
    idempotencyKey?: string;
    signal?: AbortSignal;
  } = {},
): Promise<T> {
  const accessToken = localAccessToken();
  const response = await fetch(`${apiUrl}${path}`, {
    method: options.method ?? "GET",
    headers: {
      Accept: "application/json",
      ...(options.body ? { "Content-Type": "application/json" } : {}),
      ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
      ...(options.idempotencyKey
        ? { "Idempotency-Key": options.idempotencyKey }
        : {}),
    },
    ...(options.body ? { body: JSON.stringify(options.body) } : {}),
    ...(options.signal ? { signal: options.signal } : {}),
  });

  if (!response.ok) {
    if (response.status === 401 && typeof window !== "undefined") {
      window.dispatchEvent(new Event("rigor:unauthorized"));
    }
    const payload = (await response.json().catch(() => null)) as
      | { detail?: string }
      | null;
    throw new Error(payload?.detail ?? `Mock interview API returned ${response.status}`);
  }

  return (await response.json()) as T;
}

export function getMockInterviewTemplates(signal?: AbortSignal) {
  return request<MockInterviewTemplate[]>(
    "/api/v1/mock-interviews/templates",
    signal ? { signal } : {},
  );
}

export function listMockInterviews(signal?: AbortSignal) {
  return request<MockInterviewSessionSummary[]>(
    "/api/v1/mock-interviews",
    signal ? { signal } : {},
  );
}

export function createMockInterview(
  focus: string,
  targetRole: string,
  idempotencyKey: string,
) {
  return request<MockInterviewSession>("/api/v1/mock-interviews", {
    method: "POST",
    idempotencyKey,
    body: { focus, target_role: targetRole },
  });
}

export function getMockInterview(sessionId: string, signal?: AbortSignal) {
  return request<MockInterviewSession>(
    `/api/v1/mock-interviews/${encodeURIComponent(sessionId)}`,
    signal ? { signal } : {},
  );
}

export function answerMockInterview(
  sessionId: string,
  content: string,
  idempotencyKey: string,
) {
  return request<MockInterviewSession>(
    `/api/v1/mock-interviews/${encodeURIComponent(sessionId)}/responses`,
    {
      method: "POST",
      idempotencyKey,
      body: { content },
    },
  );
}

export function updateMockInterviewState(
  sessionId: string,
  action: "pause" | "resume" | "cancel",
) {
  return request<MockInterviewSession>(
    `/api/v1/mock-interviews/${encodeURIComponent(sessionId)}/actions`,
    { method: "POST", body: { action } },
  );
}
