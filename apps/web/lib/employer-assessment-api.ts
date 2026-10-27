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
  const response = await fetch(apiUrl + path, {
    method,
    credentials: "same-origin",
    headers: {
      Accept: "application/json",
      ...(body === undefined ? {} : { "Content-Type": "application/json" }),
      ...(token ? { Authorization: "Bearer " + token } : {}),
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
