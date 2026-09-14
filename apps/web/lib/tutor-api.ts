export type TutorMode = "lesson" | "roadmap" | "practice" | "mock";
export type TutorSurface = "chat" | "code" | "whiteboard";
export type CandidateLevel = "junior" | "mid" | "senior" | "staff" | "manager";

export type WhiteboardNode = {
  id: string;
  label: string;
  kind: string | null;
  x: number | null;
  y: number | null;
};

export type WhiteboardEdge = {
  source: string;
  target: string;
  label: string | null;
};

export type WhiteboardSnapshot = {
  nodes: WhiteboardNode[];
  edges: WhiteboardEdge[];
  requirements: string[];
  notes: string[];
};

export type TutorSession = {
  id: string;
  mode: TutorMode;
  surface: TutorSurface;
  candidate_level: CandidateLevel;
  status: "active" | "ended";
  question_slug: string | null;
  title: string | null;
  provider: string | null;
  model: string | null;
  summary: string | null;
  started_at: string;
  updated_at: string;
  ended_at: string | null;
};

export type TutorEvent = {
  id: string;
  session_id: string;
  event_type: string;
  idempotency_key: string;
  payload: Record<string, unknown>;
  created_at: string;
};

export type TutorIntervention = {
  kind:
    | "observe"
    | "silent"
    | "concept_check"
    | "nudge"
    | "hint"
    | "complexity_challenge"
    | "tradeoff_challenge";
  reason: string;
  may_reveal_solution: boolean;
  should_speak: boolean;
};

export type TutorMessageResponse = {
  session_id: string;
  reply: string;
  provider: string;
  model: string;
  intervention: TutorIntervention;
};

const apiUrl = process.env.NEXT_PUBLIC_RIGOR_API_URL ?? "/api/backend";
const useLocalAccessToken = process.env.NEXT_PUBLIC_RIGOR_AUTH_MODE === "local";

async function tutorRequest<T>(
  path: string,
  options: { method?: string; body?: unknown; signal?: AbortSignal } = {},
): Promise<T> {
  const accessToken =
    !useLocalAccessToken ||
    typeof window === "undefined" ||
    typeof window.localStorage === "undefined"
      ? null
      : window.localStorage.getItem("rigor.auth.access-token");
  const response = await fetch(`${apiUrl}${path}`, {
    method: options.method ?? "GET",
    headers: {
      Accept: "application/json",
      ...(options.body ? { "Content-Type": "application/json" } : {}),
      ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
    },
    ...(options.body ? { body: JSON.stringify(options.body) } : {}),
    ...(options.signal ? { signal: options.signal } : {}),
  });
  if (!response.ok) {
    if (response.status === 401 && typeof window !== "undefined") {
      window.dispatchEvent(new Event("rigor:unauthorized"));
    }
    const body = (await response.json().catch(() => null)) as
      | { detail?: string }
      | null;
    throw new Error(body?.detail ?? `Tutor API returned ${response.status}`);
  }
  return (await response.json()) as T;
}

export function listTutorSessions(signal?: AbortSignal) {
  return tutorRequest<TutorSession[]>(
    "/api/v1/tutor/sessions",
    signal ? { signal } : {},
  );
}

export function createTutorSession(input: {
  questionSlug: string;
  candidateLevel: CandidateLevel;
}) {
  return tutorRequest<TutorSession>("/api/v1/tutor/sessions", {
    method: "POST",
    body: {
      mode: "practice",
      surface: "code",
      candidate_level: input.candidateLevel,
      question_slug: input.questionSlug,
      title: "Coding coach",
    },
  });
}

export function createWhiteboardTutorSession(input: {
  candidateLevel: CandidateLevel;
  title?: string;
}) {
  return tutorRequest<TutorSession>("/api/v1/tutor/sessions", {
    method: "POST",
    body: {
      mode: "practice",
      surface: "whiteboard",
      candidate_level: input.candidateLevel,
      question_slug: null,
      title: input.title ?? "System design lab",
    },
  });
}

export function listTutorEvents(sessionId: string, signal?: AbortSignal) {
  return tutorRequest<TutorEvent[]>(
    `/api/v1/tutor/sessions/${encodeURIComponent(sessionId)}/events`,
    signal ? { signal } : {},
  );
}

export function appendTutorEvent(
  sessionId: string,
  input: {
    eventType: string;
    idempotencyKey: string;
    payload: Record<string, unknown>;
  },
) {
  return tutorRequest<TutorEvent>(
    `/api/v1/tutor/sessions/${encodeURIComponent(sessionId)}/events`,
    {
      method: "POST",
      body: {
        event_type: input.eventType,
        idempotency_key: input.idempotencyKey,
        payload: input.payload,
      },
    },
  );
}

export function sendTutorMessage(
  sessionId: string,
  message: string,
  idempotencyKey: string,
) {
  return tutorRequest<TutorMessageResponse>(
    `/api/v1/tutor/sessions/${encodeURIComponent(sessionId)}/messages`,
    {
      method: "POST",
      body: { message, idempotency_key: idempotencyKey },
    },
  );
}

export function endTutorSession(sessionId: string) {
  return tutorRequest<TutorSession>(
    `/api/v1/tutor/sessions/${encodeURIComponent(sessionId)}/end`,
    { method: "POST", body: {} },
  );
}