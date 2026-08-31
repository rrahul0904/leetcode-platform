export type CareerInterviewQuestion = {
  category: "experience" | "technical" | "gap" | "behavioral" | "system-design";
  focus: string;
  question: string;
  coaching_note: string;
};

export type CareerJobStatus =
  | "saved"
  | "tailored"
  | "applied"
  | "screen"
  | "interview"
  | "offer"
  | "rejected"
  | "withdrawn";

export type CareerJobAnalysisInput = {
  job_title?: string;
  company?: string;
  source_url?: string;
  resume_text: string;
  job_description: string;
};

export type CareerJobAnalysis = {
  job_title: string | null;
  company: string | null;
  source_url: string | null;
  fit_score: number;
  skill_coverage: number;
  language_overlap: number;
  matched_skills: string[];
  missing_skills: string[];
  resume_skills: string[];
  priority_keywords: string[];
  strengths: string[];
  risks: string[];
  interview_questions: CareerInterviewQuestion[];
  scoring_explanation: string;
};

export type CareerSavedAnalysis = CareerJobAnalysis & {
  job_id: string;
  document_id: string;
  analysis_id: string;
  status: CareerJobStatus;
  scoring_version: string;
  created_at: string;
};

export type CareerJobSummary = {
  id: string;
  job_title: string | null;
  company: string | null;
  source_url: string | null;
  status: CareerJobStatus;
  latest_fit_score: number | null;
  matched_skills: string[];
  missing_skills: string[];
  analysis_count: number;
  last_analyzed_at: string | null;
  created_at: string;
  updated_at: string;
};

const apiUrl = process.env.NEXT_PUBLIC_RIGOR_API_URL ?? "/api/backend";
const useLocalAccessToken = process.env.NEXT_PUBLIC_RIGOR_AUTH_MODE === "local";

export class CareerApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

function accessToken() {
  return !useLocalAccessToken ||
    typeof window === "undefined" ||
    typeof window.localStorage === "undefined"
    ? null
    : window.localStorage.getItem("rigor.auth.access-token");
}

function requestHeaders() {
  const token = accessToken();
  return {
    Accept: "application/json",
    "Content-Type": "application/json",
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };
}

function notifyHistoryChanged() {
  if (typeof window !== "undefined") {
    window.dispatchEvent(new Event("careeros:history-changed"));
  }
}

async function parseResponse<T>(response: Response, fallback: string): Promise<T> {
  if (!response.ok) {
    if (response.status === 401 && typeof window !== "undefined") {
      window.dispatchEvent(new Event("rigor:unauthorized"));
    }
    let message = `${fallback} (${response.status})`;
    try {
      const payload = (await response.json()) as { detail?: string; message?: string };
      message = payload.message ?? payload.detail ?? message;
    } catch {
      // Keep the stable fallback when the upstream response has no JSON body.
    }
    throw new CareerApiError(response.status, message);
  }
  return (await response.json()) as T;
}

export async function analyzeCareerJob(
  input: CareerJobAnalysisInput,
  signal?: AbortSignal,
): Promise<CareerSavedAnalysis> {
  const response = await fetch(`${apiUrl}/api/v1/career/jobs/analyze`, {
    method: "POST",
    headers: requestHeaders(),
    body: JSON.stringify(input),
    ...(signal ? { signal } : {}),
  });
  const result = await parseResponse<CareerSavedAnalysis>(response, "CareerOS analysis failed");
  notifyHistoryChanged();
  return result;
}

export async function listCareerJobs(signal?: AbortSignal): Promise<CareerJobSummary[]> {
  const response = await fetch(`${apiUrl}/api/v1/career/jobs`, {
    headers: requestHeaders(),
    cache: "no-store",
    ...(signal ? { signal } : {}),
  });
  return parseResponse<CareerJobSummary[]>(response, "CareerOS history failed");
}

export async function updateCareerJobStatus(
  jobId: string,
  status: CareerJobStatus,
): Promise<CareerJobSummary> {
  const response = await fetch(`${apiUrl}/api/v1/career/jobs/${jobId}/status`, {
    method: "PATCH",
    headers: requestHeaders(),
    body: JSON.stringify({ status }),
  });
  const result = await parseResponse<CareerJobSummary>(
    response,
    "CareerOS status update failed",
  );
  notifyHistoryChanged();
  return result;
}
