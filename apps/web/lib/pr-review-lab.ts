export type ReviewSeverity = "info" | "minor" | "major" | "blocker";
export type ReviewVerdict = "approve" | "comment" | "request-changes";
export type DiffLineKind = "context" | "addition" | "deletion";

export type DiffLine = {
  oldLine: number | null;
  newLine: number | null;
  kind: DiffLineKind;
  content: string;
};

export type ReviewFile = {
  path: string;
  additions: number;
  deletions: number;
  lines: DiffLine[];
};

export type PublicReviewChallenge = {
  id: string;
  title: string;
  repository: string;
  pullRequest: number;
  author: string;
  difficulty: string;
  estimatedMinutes: number;
  summary: string;
  files: ReviewFile[];
};

export type ReviewComment = {
  id: string;
  sessionId: string;
  file: string;
  line: number;
  severity: ReviewSeverity;
  message: string;
  createdAt: string;
};

export type ReviewSession = {
  id: string;
  challengeId: string;
  status: "active" | "submitted";
  verdict: ReviewVerdict | null;
  score: number | null;
  recall: number | null;
  precision: number | null;
  severityAccuracy: number | null;
  reasoningQuality: number | null;
  verdictCorrect: boolean | null;
  startedAt: string;
  updatedAt: string;
  submittedAt: string | null;
};

export type ReviewSessionDetail = {
  session: ReviewSession;
  comments: ReviewComment[];
};

export type GradedFinding = {
  id: string;
  file: string;
  line: number;
  severity: ReviewSeverity;
  title: string;
  explanation: string;
};

export type ReviewGrade = {
  score: number;
  caught: GradedFinding[];
  missed: GradedFinding[];
  falsePositiveCount: number;
  severityAccuracy: number;
  precision: number;
  recall: number;
  reasoningQuality: number;
  verdictCorrect: boolean;
};

export type ReviewSubmission = {
  session: ReviewSession;
  grade: ReviewGrade;
};
