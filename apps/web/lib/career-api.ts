export type CareerInterviewQuestion = {
  category: "experience" | "technical" | "gap" | "behavioral" | "system-design";
  focus: string;
  question: string;
  coaching_note: string;
};

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

export async function analyzeCareerJob(
  input: CareerJobAnalysisInput,
  signal?: AbortSignal,
): Promise<CareerJobAnalysis> {
  const accessToken =
    !useLocalAccessToken ||
    typeof window === "undefined" ||
    typeof window.localStorage === "undefined"
      ? null
      : window.localStorage.getItem("rigor.auth.access-token");

  const response = await fetch(`${apiUrl}/api/v1/career/jobs/analyze`, {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
      ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
    },
    body: JSON.stringify(input),
    signal,
  });

  if (!response.ok) {
    if (response.status === 401 && typeof window !== "undefined") {
      window.dispatchEvent(new Event("rigor:unauthorized"));
    }
    let message = `CareerOS analysis failed (${response.status})`;
    try {
      const payload = (await response.json()) as { detail?: string; message?: string };
      message = payload.message ?? payload.detail ?? message;
    } catch {
      // Keep the stable fallback when the upstream response has no JSON body.
    }
    throw new CareerApiError(response.status, message);
  }

  return (await response.json()) as CareerJobAnalysis;
}
