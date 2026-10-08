import type { MockInterviewSession } from "./mock-interview-api";

const apiUrl = process.env.NEXT_PUBLIC_RIGOR_API_URL ?? "/api/backend";
const authMode = process.env.NEXT_PUBLIC_RIGOR_AUTH_MODE ?? "clerk";

export type ThinkAloudMode = "practice" | "assessment";
export type ThinkAloudFloorOwner = "candidate" | "interviewer" | "coach" | "none";

export type ThinkAloudEvent = {
  sequence_number: number;
  role: string;
  phase: string;
  event_type: string;
  content: string;
  payload: Record<string, unknown>;
  created_at: string;
};

export type ThinkAloudControlState = {
  session_id: string;
  mode: ThinkAloudMode;
  floor_owner: ThinkAloudFloorOwner;
  coaching_active: boolean;
  provider_connected: boolean;
  events: ThinkAloudEvent[];
  canvas: ThinkAloudEvent[];
};

export type ThinkAloudSession = {
  session: MockInterviewSession;
  control: ThinkAloudControlState;
};

export type CanvasMutation = {
  kind: "add_component" | "update_component" | "remove_component" | "connect" | "note";
  label: string;
  component_type?: string | null;
  payload?: Record<string, unknown>;
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
    throw new Error(payload?.detail ?? `Think Aloud API returned ${response.status}`);
  }

  return (await response.json()) as T;
}

export function createThinkAloudSession(
  focus: string,
  targetRole: string,
  mode: ThinkAloudMode,
  idempotencyKey: string,
) {
  return request<ThinkAloudSession>("/api/v1/think-aloud/sessions", {
    method: "POST",
    idempotencyKey,
    body: { focus, target_role: targetRole, mode },
  });
}

export function getThinkAloudSession(sessionId: string, signal?: AbortSignal) {
  return request<ThinkAloudSession>(
    `/api/v1/think-aloud/sessions/${encodeURIComponent(sessionId)}`,
    signal ? { signal } : {},
  );
}

export function commitThinkAloudTurn(
  sessionId: string,
  content: string,
  idempotencyKey: string,
) {
  return request<ThinkAloudSession>(
    `/api/v1/think-aloud/sessions/${encodeURIComponent(sessionId)}/turns/commit`,
    {
      method: "POST",
      idempotencyKey,
      body: { content },
    },
  );
}

export function recordThinkAloudEvent(
  sessionId: string,
  eventType:
    | "candidate_silence"
    | "candidate_interrupt"
    | "provider_disconnected"
    | "provider_reconnected",
  payload: Record<string, unknown>,
  idempotencyKey: string,
) {
  return request<ThinkAloudSession>(
    `/api/v1/think-aloud/sessions/${encodeURIComponent(sessionId)}/events`,
    {
      method: "POST",
      idempotencyKey,
      body: { event_type: eventType, payload },
    },
  );
}

export function mutateThinkAloudCanvas(
  sessionId: string,
  mutation: CanvasMutation,
  idempotencyKey: string,
) {
  return request<ThinkAloudSession>(
    `/api/v1/think-aloud/sessions/${encodeURIComponent(sessionId)}/canvas`,
    {
      method: "POST",
      idempotencyKey,
      body: mutation,
    },
  );
}

export function startThinkAloudCoaching(
  sessionId: string,
  question: string | null,
  idempotencyKey: string,
) {
  return request<ThinkAloudSession>(
    `/api/v1/think-aloud/sessions/${encodeURIComponent(sessionId)}/coaching`,
    {
      method: "POST",
      idempotencyKey,
      body: { question },
    },
  );
}

export function resumeThinkAloudCoaching(
  sessionId: string,
  idempotencyKey: string,
) {
  return request<ThinkAloudSession>(
    `/api/v1/think-aloud/sessions/${encodeURIComponent(sessionId)}/coaching/resume`,
    {
      method: "POST",
      idempotencyKey,
      body: {},
    },
  );
}
