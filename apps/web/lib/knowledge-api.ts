const apiUrl = process.env.NEXT_PUBLIC_RIGOR_API_URL ?? "http://localhost:8002";

export type Availability = "runnable" | "published" | "reference_only";
export type CanonicalClassification =
  | "canonical_candidate"
  | "legitimate_variant"
  | "near_concept_duplicate"
  | "reference_only"
  | "runnable_candidate";

export type KnowledgeStats = {
  problems: number;
  published_problems: number;
  metadata_only_problems: number;
  python_solutions: number;
  javascript_solutions: number;
  sql_solutions: number;
  companies: number;
  topics: number;
  system_design_articles: number;
  source_files: number;
};

export type KnowledgeCatalogStats = {
  problems: number;
  runnable_problems: number;
  published_problems: number;
  reference_only_problems: number;
  statement_backed_problems: number;
  python_solutions: number;
  javascript_solutions: number;
  sql_solutions: number;
  companies: number;
  topics: number;
  system_design_articles: number;
  source_files: number;
  runtime_verified_links: number;
};

export type ProblemSummary = {
  id: string;
  canonical_key: string;
  external_id: string | null;
  title: string;
  slug: string;
  summary: string | null;
  difficulty: string | null;
  source_url: string | null;
  publication_status: string;
  review_status: string;
  availability: Availability;
  acceptance_rate: number | null;
  popularity: number | null;
  languages: string[];
  topics: string[];
  companies: string[];
  platform: string | null;
  subtopic: string | null;
  seniority: string | null;
  industry: string | null;
  canonical_classification: string | null;
  practice_question_slug: string | null;
  practice_runtime: "python" | "postgresql" | null;
};

export type ProblemDetail = ProblemSummary & {
  description: string | null;
  input_format: string | null;
  output_format: string | null;
  examples: unknown[];
  constraints: unknown[];
  hints: unknown[];
  editorial_available: boolean;
  solution_count: number;
};

export type SolutionVariant = {
  id: string;
  approach_id: string;
  approach_name: string;
  language: string;
  runtime: string | null;
  source_code: string;
  explanation: string | null;
  time_complexity: string | null;
  space_complexity: string | null;
  is_executable: boolean;
};

export type ProblemPage = {
  items: ProblemSummary[];
  page: number;
  page_size: number;
  total: number;
  has_next: boolean;
};

export type CompanySummary = {
  id: string;
  slug: string;
  name: string;
  problem_count: number;
  easy_count: number;
  medium_count: number;
  hard_count: number;
  average_frequency: number | null;
};

export type SystemDesignSummary = {
  id: string;
  slug: string;
  title: string;
  headings: string[];
  image_count: number;
  publication_status: string;
};

export type SystemDesignDetail = SystemDesignSummary & {
  body: string;
  image_paths: string[];
};

function accessToken() {
  if (typeof window === "undefined" || typeof window.localStorage === "undefined") {
    return null;
  }
  return window.localStorage.getItem("rigor.auth.access-token");
}

async function request<T>(path: string, signal?: AbortSignal): Promise<T> {
  const token = accessToken();
  const response = await fetch(`${apiUrl}${path}`, {
    headers: {
      Accept: "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    ...(signal ? { signal } : {}),
  });
  if (!response.ok) {
    if (response.status === 401 && typeof window !== "undefined") {
      window.dispatchEvent(new Event("rigor:unauthorized"));
    }
    throw new Error(`Knowledge API returned ${response.status}`);
  }
  return (await response.json()) as T;
}

export function getKnowledgeStats(signal?: AbortSignal) {
  return request<KnowledgeStats>("/api/v1/knowledge/stats", signal);
}

export function getKnowledgeCatalogStats(signal?: AbortSignal) {
  return request<KnowledgeCatalogStats>("/api/v1/knowledge/catalog/stats", signal);
}

export function getKnowledgeProblems(
  filters: {
    query?: string;
    difficulty?: string;
    language?: string;
    company?: string;
    topic?: string;
    platform?: string;
    subtopic?: string;
    seniority?: string;
    industry?: string;
    canonicalClassification?: CanonicalClassification | "";
    availability?: Availability | "";
    sort?: string;
    page?: number;
    pageSize?: number;
  },
  signal?: AbortSignal,
) {
  const parameters = new URLSearchParams({
    page: String(filters.page ?? 1),
    page_size: String(filters.pageSize ?? 30),
    sort: filters.sort ?? "relevance",
  });
  for (const [key, value] of Object.entries({
    query: filters.query,
    difficulty: filters.difficulty,
    language: filters.language,
    company: filters.company,
    topic: filters.topic,
    platform: filters.platform,
    subtopic: filters.subtopic,
    seniority: filters.seniority,
    industry: filters.industry,
    canonical_classification: filters.canonicalClassification,
    availability: filters.availability,
  })) {
    if (value) parameters.set(key, value);
  }
  return request<ProblemPage>(
    `/api/v1/knowledge/catalog/problems?${parameters.toString()}`,
    signal,
  );
}

export function getKnowledgeProblem(slug: string, signal?: AbortSignal) {
  return request<ProblemDetail>(
    `/api/v1/knowledge/catalog/problems/${encodeURIComponent(slug)}`,
    signal,
  );
}

export function getKnowledgeSolutions(
  slug: string,
  language?: string,
  signal?: AbortSignal,
) {
  const parameters = new URLSearchParams();
  if (language) parameters.set("language", language);
  const query = parameters.size ? `?${parameters.toString()}` : "";
  return request<SolutionVariant[]>(
    `/api/v1/knowledge/problems/${encodeURIComponent(slug)}/solutions${query}`,
    signal,
  );
}

export function getKnowledgeCompanies(signal?: AbortSignal) {
  return request<CompanySummary[]>("/api/v1/knowledge/companies", signal);
}

export function getSystemDesignLibrary(signal?: AbortSignal) {
  return request<SystemDesignSummary[]>("/api/v1/knowledge/system-design", signal);
}

export function getSystemDesignArticle(slug: string, signal?: AbortSignal) {
  return request<SystemDesignDetail>(
    `/api/v1/knowledge/system-design/${encodeURIComponent(slug)}`,
    signal,
  );
}
