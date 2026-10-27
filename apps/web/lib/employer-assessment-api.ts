const apiUrl = process.env.NEXT_PUBLIC_RIGOR_API_URL ?? "/api/backend";
const authMode = process.env.NEXT_PUBLIC_RIGOR_AUTH_MODE ?? "clerk";

export type AssessmentQuestion = {
  number: number;
  kind: "code" | "written" | "multiple_choice";
  prompt: string;
  marks: number;
  options: string[];
};

export type AssessmentAttempt = {
  id: string;
  assessment_version_id: string;
  status: "created" | "in_progress" | "submitted" | "expired" | "cancelled";
  started_at: string | null;
  deadline_at: string | null;
  submitted_at: string | null;
  duration_minutes: number;
  questions: AssessmentQuestion[];
  answers: Record<string, string>;
};

export type EmployerAssessment = {
  id: string;
  slug: string;
  version: number;
  title: string;
  duration_minutes: number;
  maximum_marks: number;
  status: string;
  content_sha256: string;
  questions: AssessmentQuestion[];
};

function localAccessToken() {
  if (authMode !== "local" || typeof window === "undefined") return null;
  return window.localStorage.getItem("rigor.auth.access-token");
}

async function request<T>(
  path: string,
  method = "GET",
  body?: unknown,
): Promise<T> {
  const token = localAccessToken();
  const selectedOrg =
    typeof window !== "undefined" &&
    path.startsWith("/api/v1/employer/") &&
    path !== "/api/v1/employer/organizations"
      ? window.localStorage.getItem("rigor.employer.organization-id")
      : null;
  const response = await fetch(apiUrl + path, {
    method,
    credentials: "same-origin",
    headers: {
      Accept: "application/json",
      ...(body === undefined ? {} : { "Content-Type": "application/json" }),
      ...(token ? { Authorization: "Bearer " + token } : {}),
      ...(selectedOrg ? { "X-Rigor-Organization-ID": selectedOrg } : {}),
    },
    ...(body === undefined ? {} : { body: JSON.stringify(body) }),
    cache: "no-store",
  });
  if (!response.ok) {
    if (response.status === 401 && typeof window !== "undefined") {
      window.dispatchEvent(new Event("rigor:unauthorized"));
    }
    const payload = (await response.json().catch(() => null)) as
      | { detail?: string }
      | null;
    throw new Error(payload?.detail ?? "Assessment API returned " + response.status);
  }
  return (await response.json()) as T;
}

export function acceptInterviewInvite(invitationId: string, secret: string) {
  return request<AssessmentAttempt>("/api/v1/assessment-invitations/accept", "POST", {
    invitation_id: invitationId,
    acceptance_secret: secret,
  });
}

export function getInterviewAttempt(attemptId: string) {
  return request<AssessmentAttempt>(
    "/api/v1/assessment-attempts/" + encodeURIComponent(attemptId),
  );
}

export function saveInterviewAnswer(
  attemptId: string, questionNumber: number, answer: string,
) {
  return request<AssessmentAttempt>(
    "/api/v1/assessment-attempts/" + encodeURIComponent(attemptId) + "/responses",
    "PUT",
    { question_number: questionNumber, answer_text: answer },
  );
}

export function submitInterviewAttempt(attemptId: string) {
  return request<AssessmentAttempt>(
    "/api/v1/assessment-attempts/" + encodeURIComponent(attemptId) + "/submit",
    "POST",
  );
}

export function listEmployerAssessments() {
  return request<EmployerAssessment[]>("/api/v1/employer/assessments");
}

export function createEmployerAssessment(payload: {
  slug: string;
  title: string;
  duration_minutes: number;
  questions: AssessmentQuestion[];
}) {
  return request<EmployerAssessment>("/api/v1/employer/assessments", "POST", payload);
}

export function publishEmployerAssessment(
  assessmentId: string,
  evidence: { rights_evidence: string; technical_evidence: string; editorial_evidence: string },
) {
  return request<EmployerAssessment>(
    "/api/v1/employer/assessments/" + encodeURIComponent(assessmentId) + "/publish",
    "POST",
    evidence,
  );
}

export type EmployerInvitation = {
  id: string;
  candidate_id: string;
  expires_at: string;
  acceptance_secret: string;
};

export function inviteEmployerCandidate(
  assessmentId: string, candidateId: string, expiresInHours: number,
) {
  return request<EmployerInvitation>(
    "/api/v1/employer/assessments/" + encodeURIComponent(assessmentId) + "/invitations",
    "POST",
    { candidate_id: candidateId, expires_in_hours: expiresInHours },
  );
}


export type EmployerAttemptSummary = {
  id: string;
  assessment_version_id: string;
  candidate_id: string;
  status: string;
  started_at: string | null;
  deadline_at: string | null;
  submitted_at: string | null;
};

export type EmployerAttemptDetail = {
  attempt: EmployerAttemptSummary;
  questions: AssessmentQuestion[];
  answers: Array<{
    question_number: number;
    answer_text: string;
    updated_at: string;
  }>;
  maximum_marks: number;
  content_sha256: string;
};

export type HumanQuestionScore = {
  question_number: number;
  awarded_marks: number;
  evidence_note: string;
};

export type SubmittedHumanReview = {
  review_id: string;
  attempt_id: string;
  reviewer_id: string;
  status: "submitted";
  awarded_marks: number;
  maximum_marks: number;
  hiring_decision: null;
};

export function listEmployerAttempts(assessmentId: string) {
  return request<EmployerAttemptSummary[]>(
    "/api/v1/employer/assessments/" + encodeURIComponent(assessmentId) + "/attempts",
  );
}

export function getEmployerAttempt(attemptId: string) {
  return request<EmployerAttemptDetail>(
    "/api/v1/employer/attempts/" + encodeURIComponent(attemptId),
  );
}

export function submitEmployerHumanReview(
  attemptId: string, scores: HumanQuestionScore[], overallNotes: string,
) {
  return request<SubmittedHumanReview>(
    "/api/v1/employer/attempts/" + encodeURIComponent(attemptId) + "/reviews",
    "POST",
    { scores, overall_notes: overallNotes },
  );
}


export type EmployerOrganization = {
  id: string;
  name: string;
  slug: string;
  membership_role: string;
};

export type EmployerMember = {
  user_id: string;
  role: string;
  status: string;
};

export function selectedEmployerOrganization() {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem("rigor.employer.organization-id");
}

export function selectEmployerOrganization(organizationId: string) {
  if (typeof window !== "undefined") {
    window.localStorage.setItem("rigor.employer.organization-id", organizationId);
  }
}

export function listEmployerOrganizations() {
  return request<EmployerOrganization[]>("/api/v1/employer/organizations");
}

export function createEmployerOrganization(name: string, slug: string) {
  return request<EmployerOrganization>(
    "/api/v1/employer/organizations", "POST", { name, slug },
  );
}

export function listEmployerMembers(organizationId: string) {
  return request<EmployerMember[]>(
    "/api/v1/employer/organizations/" + encodeURIComponent(organizationId) + "/members",
  );
}

export function addEmployerMember(
  organizationId: string,
  userId: string,
  role: "admin" | "recruiter" | "interviewer" | "reviewer",
) {
  return request<EmployerMember>(
    "/api/v1/employer/organizations/" + encodeURIComponent(organizationId) + "/members",
    "POST",
    { user_id: userId, role },
  );
}


export type PrivateAnswerKey = {
  assessment_version_id: string;
  source_sha256: string;
  mcq_answers: Record<number, "A" | "B" | "C" | "D">;
  reviewer_guidance: string;
};

export function savePrivateAnswerKey(
  assessmentId: string,
  mcqAnswers: Record<number, "A" | "B" | "C" | "D">,
  reviewerGuidance: string,
) {
  return request<PrivateAnswerKey>(
    "/api/v1/employer/assessments/" + encodeURIComponent(assessmentId) + "/private-key",
    "PUT",
    { mcq_answers: mcqAnswers, reviewer_guidance: reviewerGuidance },
  );
}

export type ProvisionalMCQScore = {
  assessment_attempt_id: string;
  source_sha256: string;
  mcq_awarded_marks: number;
  mcq_maximum_marks: number;
  human_review_pending_marks: number;
  scoring_status: "provisional_mcq_only";
  hiring_decision: null;
};

export function provisionalMCQScore(attemptId: string) {
  return request<ProvisionalMCQScore>(
    "/api/v1/employer/attempts/" + encodeURIComponent(attemptId) + "/provisional-mcq-score",
  );
}

export function listCandidateAssessmentAttempts() {
  return request<AssessmentAttempt[]>("/api/v1/assessment-attempts");
}


export type EmployerInvitationStatus = {
  id: string;
  assessment_version_id: string;
  candidate_id: string;
  state: "pending" | "accepted" | "revoked" | "expired";
  expires_at: string;
  consumed_at: string | null;
  created_at: string;
};

export function listAssessmentInvitations(assessmentId: string) {
  return request<EmployerInvitationStatus[]>(
    "/api/v1/employer/assessments/" + encodeURIComponent(assessmentId) + "/invitations",
  );
}

export function revokeAssessmentInvitation(invitationId: string) {
  return request<EmployerInvitationStatus>(
    "/api/v1/employer/invitations/" + encodeURIComponent(invitationId) + "/revoke",
    "POST",
  );
}


export type EmployerAIInterviewTurn = {
  sequence_number: number;
  role: "candidate" | "interviewer";
  content: string;
  request_id: string;
  created_at: string;
};

export type EmployerAIInterview = {
  id: string;
  attempt_id: string;
  status: "active" | "withdrawn" | "completed";
  consent_version: string;
  consent_at: string;
  turn_count: number;
  provider_configured: boolean;
  messages: EmployerAIInterviewTurn[];
};

export function consentToEmployerAIInterview(attemptId: string) {
  return request<EmployerAIInterview>(
    "/api/v1/assessment-attempts/" + encodeURIComponent(attemptId) + "/ai-interview/consent",
    "POST",
    { agree_to_ai_processing: true },
  );
}

export function getEmployerAIInterview(attemptId: string) {
  return request<EmployerAIInterview>(
    "/api/v1/assessment-attempts/" + encodeURIComponent(attemptId) + "/ai-interview",
  );
}

export function sendEmployerAIInterviewMessage(
  attemptId: string, message: string, requestId: string,
) {
  return request<EmployerAIInterview>(
    "/api/v1/assessment-attempts/" + encodeURIComponent(attemptId) + "/ai-interview/messages",
    "POST", { message, request_id: requestId },
  );
}

export function withdrawEmployerAIInterview(attemptId: string) {
  return request<EmployerAIInterview>(
    "/api/v1/assessment-attempts/" + encodeURIComponent(attemptId) + "/ai-interview/withdraw",
    "POST",
  );
}
