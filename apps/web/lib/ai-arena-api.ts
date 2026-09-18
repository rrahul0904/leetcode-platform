import type {
  AsyncExecutionView,
  SubmissionRuntime,
} from "@/lib/async-execution";

const apiUrl = process.env.NEXT_PUBLIC_RIGOR_API_URL ?? "/api/backend";
const authMode = process.env.NEXT_PUBLIC_RIGOR_AUTH_MODE ?? "clerk";

export type ArenaChallenge = {
  slug: string;
  title: string;
  difficulty: string;
  problem_statement: string;
  constraints: string[];
  public_examples: unknown[];
  starter_code: string;
  public_test_count: number;
  hidden_test_count: number;
};

export type ArenaGeneration = {
  id: string;
  challenge_slug: string;
  prompt: string;
  generated_code: string;
  provider: string;
  model: string;
};

export type ArenaScore = {
  correctness: number;
  performance: number;
  quality: number;
  efficiency: number;
  total: number;
};

export type ArenaResult = {
  id: string;
  generation_id: string;
  submission_id: string;
  challenge_slug: string;
  score: ArenaScore;
  rating_delta: number;
  rating_after: number;
  tier: string;
};

export type ArenaProfile = {
  display_name: string;
  rating: number;
  tier: string;
  solved_count: number;
  submission_count: number;
};

export type ArenaLeaderboardRow = ArenaProfile & { rank: number };

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

async function arenaRequest<T>(
  path: string,
  options: {
    method?: string;
    body?: unknown;
    headers?: Record<string, string>;
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
      ...options.headers,
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
    throw new Error(payload?.detail ?? `AI Arena API returned ${response.status}`);
  }
  return (await response.json()) as T;
}

export function getArenaChallenges(signal?: AbortSignal) {
  return arenaRequest<ArenaChallenge[]>(
    "/api/v1/arena/challenges",
    signal ? { signal } : {},
  );
}

export function getArenaProfile(signal?: AbortSignal) {
  return arenaRequest<ArenaProfile>("/api/v1/arena/me", signal ? { signal } : {});
}

export function getArenaLeaderboard(signal?: AbortSignal) {
  return arenaRequest<ArenaLeaderboardRow[]>(
    "/api/v1/arena/leaderboard",
    signal ? { signal } : {},
  );
}

export function generateArenaCode(
  challengeSlug: string,
  prompt: string,
  idempotencyKey: string,
) {
  return arenaRequest<ArenaGeneration>("/api/v1/arena/generate", {
    method: "POST",
    headers: { "Idempotency-Key": idempotencyKey },
    body: { challenge_slug: challengeSlug, prompt },
  });
}

export function finalizeArenaSubmission(generationId: string, submissionId: string) {
  return arenaRequest<ArenaResult>("/api/v1/arena/finalize", {
    method: "POST",
    body: { generation_id: generationId, submission_id: submissionId },
  });
}

export function isArenaExecutionComplete(execution: AsyncExecutionView) {
  return ["COMPLETED", "FAILED", "TIMEOUT", "CANCELLED"].includes(execution.status);
}

export const arenaRuntime: SubmissionRuntime = "python3.13";
