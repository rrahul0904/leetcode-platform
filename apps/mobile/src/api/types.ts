import type { components } from "@rigor/api-client/schema";

export type AuthenticatedPrincipal = components["schemas"]["AuthenticatedPrincipal"];
export type CandidateProfile = components["schemas"]["CandidateProfile"];
export type CandidateProfileInput = components["schemas"]["CandidateProfileInput"];
export type CatalogQuestion = components["schemas"]["CatalogQuestion"];
export type CatalogQuestionPage = components["schemas"]["Page_CatalogQuestion_"];
export type CandidateQuestionDetail = components["schemas"]["CandidateQuestionDetail"];
export type PracticeSession = components["schemas"]["PracticeSessionView"];
export type PracticeHint = components["schemas"]["PracticeHint"];
export type ExecutionResult = components["schemas"]["ExecutionResult"];
export type CandidateSubmission = components["schemas"]["CandidateSubmission"];
export type CandidateReadiness = components["schemas"]["CandidateReadiness"];
export type CompetencyReadiness = components["schemas"]["CompetencyReadiness"];
export type NextAction = components["schemas"]["NextAction"];

// The durable execution API is intentionally modeled here instead of relying on a
// generated OpenAPI snapshot. This keeps the native client fail-closed when the
// execution plane evolves independently from older synchronous submission models.
export type AsyncExecutionStatus =
  | "QUEUED"
  | "DISPATCHING"
  | "RUNNING"
  | "COMPLETED"
  | "FAILED"
  | "TIMEOUT"
  | "CANCELLED";

export interface AsyncPublicTestResult {
  test_id: string;
  name: string;
  passed: boolean;
  expected?: unknown;
  actual?: unknown;
  error_category?: string | null;
}

export interface AsyncExecutionResult {
  public_results: AsyncPublicTestResult[];
  hidden_total: number;
  hidden_passed: number;
  stdout: string;
  stderr: string;
  candidate_message: string | null;
}

export interface ExecutionAccepted {
  execution_id: string;
  submission_id: string | null;
  execution_type: string;
  status: AsyncExecutionStatus;
  attempt: number;
  created_at: string;
  status_url: string;
  duplicate: boolean;
}

export interface ExecutionView {
  execution_id: string;
  submission_id: string | null;
  status: AsyncExecutionStatus;
  execution_type: string;
  runtime: string;
  attempt: number;
  created_at: string;
  queued_at: string;
  dispatch_started_at: string | null;
  running_at: string | null;
  completed_at: string | null;
  runtime_ms: number | null;
  memory_peak_bytes: number | null;
  result: AsyncExecutionResult | null;
  error: string | null;
}


export interface MockInterviewTemplate {
  slug: string;
  label: string;
  description: string;
  competencies: string[];
  phases: Array<{ slug: string; label: string }>;
}

export interface MockInterviewMessage {
  id: string;
  session_id: string;
  sequence_number: number;
  role: string;
  phase: string;
  content: string;
  evidence: Record<string, unknown>;
  created_at: string;
}

export interface MockInterviewReport {
  overall_score: number;
  rubric_evidence: Array<Record<string, unknown>>;
  strengths: string[];
  growth_areas: string[];
  next_steps: string[];
}

export type MockInterviewStatus =
  | "CREATED"
  | "READY"
  | "IN_PROGRESS"
  | "PAUSED"
  | "COMPLETED"
  | "CANCELLED";

export interface MockInterviewSessionSummary {
  id: string;
  interview_type: string;
  target_role: string;
  focus: string;
  focus_label: string;
  status: MockInterviewStatus;
  current_phase: string;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface MockInterviewSession extends MockInterviewSessionSummary {
  messages: MockInterviewMessage[];
  report: MockInterviewReport | null;
}
