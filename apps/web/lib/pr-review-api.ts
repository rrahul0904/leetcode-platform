import type {
  DiffLineKind,
  PublicReviewChallenge,
  ReviewComment,
  ReviewGrade,
  ReviewSession,
  ReviewSessionDetail,
  ReviewSeverity,
  ReviewSubmission,
  ReviewVerdict,
} from "./pr-review-lab";

const apiUrl = process.env.NEXT_PUBLIC_RIGOR_API_URL ?? "/api/backend";
const useLocalAccessToken = process.env.NEXT_PUBLIC_RIGOR_AUTH_MODE === "local";

type RawChallenge = {
  id: string;
  title: string;
  repository: string;
  pull_request: number;
  author: string;
  difficulty: string;
  estimated_minutes: number;
  summary: string;
  files: Array<{
    path: string;
    additions: number;
    deletions: number;
    lines: Array<{
      old_line: number | null;
      new_line: number | null;
      kind: DiffLineKind;
      content: string;
    }>;
  }>;
};

type RawSession = {
  id: string;
  challenge_id: string;
  status: "active" | "submitted";
  verdict: ReviewVerdict | null;
  score: number | null;
  recall: number | null;
  precision: number | null;
  severity_accuracy: number | null;
  reasoning_quality: number | null;
  verdict_correct: boolean | null;
  started_at: string;
  updated_at: string;
  submitted_at: string | null;
};

type RawComment = {
  id: string;
  session_id: string;
  file: string;
  line: number;
  severity: ReviewSeverity;
  message: string;
  created_at: string;
};

type RawGrade = {
  score: number;
  caught: ReviewGrade["caught"];
  missed: ReviewGrade["missed"];
  false_positive_count: number;
  severity_accuracy: number;
  precision: number;
  recall: number;
  reasoning_quality: number;
  verdict_correct: boolean;
};

type RawSessionDetail = {
  session: RawSession;
  comments: RawComment[];
};

type RawSubmission = {
  session: RawSession;
  grade: RawGrade;
};

async function reviewRequest<T>(
  path: string,
  options: {
    method?: string;
    body?: unknown;
    signal?: AbortSignal;
  } = {},
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
    throw new Error(body?.detail ?? `PR Review API returned ${response.status}`);
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}

function challengeFromRaw(raw: RawChallenge): PublicReviewChallenge {
  return {
    id: raw.id,
    title: raw.title,
    repository: raw.repository,
    pullRequest: raw.pull_request,
    author: raw.author,
    difficulty: raw.difficulty,
    estimatedMinutes: raw.estimated_minutes,
    summary: raw.summary,
    files: raw.files.map((file) => ({
      path: file.path,
      additions: file.additions,
      deletions: file.deletions,
      lines: file.lines.map((line) => ({
        oldLine: line.old_line,
        newLine: line.new_line,
        kind: line.kind,
        content: line.content,
      })),
    })),
  };
}

function sessionFromRaw(raw: RawSession): ReviewSession {
  return {
    id: raw.id,
    challengeId: raw.challenge_id,
    status: raw.status,
    verdict: raw.verdict,
    score: raw.score,
    recall: raw.recall,
    precision: raw.precision,
    severityAccuracy: raw.severity_accuracy,
    reasoningQuality: raw.reasoning_quality,
    verdictCorrect: raw.verdict_correct,
    startedAt: raw.started_at,
    updatedAt: raw.updated_at,
    submittedAt: raw.submitted_at,
  };
}

function commentFromRaw(raw: RawComment): ReviewComment {
  return {
    id: raw.id,
    sessionId: raw.session_id,
    file: raw.file,
    line: raw.line,
    severity: raw.severity,
    message: raw.message,
    createdAt: raw.created_at,
  };
}

function gradeFromRaw(raw: RawGrade): ReviewGrade {
  return {
    score: raw.score,
    caught: raw.caught,
    missed: raw.missed,
    falsePositiveCount: raw.false_positive_count,
    severityAccuracy: raw.severity_accuracy,
    precision: raw.precision,
    recall: raw.recall,
    reasoningQuality: raw.reasoning_quality,
    verdictCorrect: raw.verdict_correct,
  };
}

export async function getReviewChallenge(
  challengeId: string,
  signal?: AbortSignal,
): Promise<PublicReviewChallenge> {
  const raw = await reviewRequest<RawChallenge>(
    `/api/v1/pr-review/challenges/${encodeURIComponent(challengeId)}`,
    signal ? { signal } : {},
  );
  return challengeFromRaw(raw);
}

export async function listReviewSessions(
  signal?: AbortSignal,
): Promise<ReviewSession[]> {
  const rows = await reviewRequest<RawSession[]>(
    "/api/v1/pr-review/sessions",
    signal ? { signal } : {},
  );
  return rows.map(sessionFromRaw);
}

export async function createReviewSession(
  challengeId: string,
): Promise<ReviewSession> {
  const raw = await reviewRequest<RawSession>("/api/v1/pr-review/sessions", {
    method: "POST",
    body: { challenge_id: challengeId },
  });
  return sessionFromRaw(raw);
}

export async function getReviewSession(
  sessionId: string,
  signal?: AbortSignal,
): Promise<ReviewSessionDetail> {
  const raw = await reviewRequest<RawSessionDetail>(
    `/api/v1/pr-review/sessions/${encodeURIComponent(sessionId)}`,
    signal ? { signal } : {},
  );
  return {
    session: sessionFromRaw(raw.session),
    comments: raw.comments.map(commentFromRaw),
  };
}

export async function createReviewComment(
  sessionId: string,
  input: {
    file: string;
    line: number;
    severity: ReviewSeverity;
    message: string;
  },
): Promise<ReviewComment> {
  const raw = await reviewRequest<RawComment>(
    `/api/v1/pr-review/sessions/${encodeURIComponent(sessionId)}/comments`,
    {
      method: "POST",
      body: input,
    },
  );
  return commentFromRaw(raw);
}

export function deleteReviewComment(
  sessionId: string,
  commentId: string,
): Promise<void> {
  return reviewRequest<void>(
    `/api/v1/pr-review/sessions/${encodeURIComponent(sessionId)}`
      + `/comments/${encodeURIComponent(commentId)}`,
    { method: "DELETE" },
  );
}

export async function submitReviewSession(
  sessionId: string,
  verdict: ReviewVerdict,
): Promise<ReviewSubmission> {
  const raw = await reviewRequest<RawSubmission>(
    `/api/v1/pr-review/sessions/${encodeURIComponent(sessionId)}/submit`,
    {
      method: "POST",
      body: { verdict },
    },
  );
  return {
    session: sessionFromRaw(raw.session),
    grade: gradeFromRaw(raw.grade),
  };
}
