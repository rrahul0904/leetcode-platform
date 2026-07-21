import type { components } from "@rigor/api-client/schema";

export type ContentStats = components["schemas"]["ContentStats"];
export type ManifestQuestion = components["schemas"]["ManifestQuestion"];
export type QuestionPage = components["schemas"]["Page_ManifestQuestion_"];
export type CatalogQuestion = components["schemas"]["CatalogQuestion"];
export type CatalogQuestionPage =
  components["schemas"]["Page_CatalogQuestion_"];
export type CandidateQuestionDetail =
  components["schemas"]["CandidateQuestionDetail"];
export type CandidateProfile = components["schemas"]["CandidateProfile"];
export type CandidateProfileInput =
  components["schemas"]["CandidateProfileInput"];
export type ReviewQueueItem = components["schemas"]["ReviewQueueItem"];
export type ReviewActionResult = components["schemas"]["ReviewActionResult"];
export type ReviewKind = components["schemas"]["ReviewKind"];
export type ReviewOutcome = components["schemas"]["ReviewOutcome"];
export type ContinuousCoverageStats =
  components["schemas"]["ContinuousCoverageStats"];
export type SourceRegistryRecord =
  components["schemas"]["SourceRegistryRecord"];
export type SourceRegistryInput = components["schemas"]["SourceRegistryInput"];
export type SourceReviewInput = components["schemas"]["SourceReviewInput"];
export type SourceSyncResult = components["schemas"]["SourceSyncResult"];
export type CompetencyCoverage = components["schemas"]["CompetencyCoverage"];
export type ExternalReferencePage =
  components["schemas"]["Page_ExternalReference_"];
export type ExternalReference = components["schemas"]["ExternalReference"];
export type ExternalReferenceFacets =
  components["schemas"]["ExternalReferenceFacets"];
export type PracticeCatalogSummary =
  components["schemas"]["PracticeCatalogSummary"];
export type CatalogSourceStatus = components["schemas"]["CatalogSourceStatus"];
export type ContentImportReport = components["schemas"]["ContentImportReport"];
export type ContentImportSummary =
  components["schemas"]["ContentImportSummary"];
export type ContentFactoryBatchInput =
  components["schemas"]["ContentFactoryBatchInput"];
export type AdminQuestionRecord = components["schemas"]["AdminQuestionRecord"];
export type DuplicateCandidateRecord =
  components["schemas"]["DuplicateCandidateRecord"];
export type QuestionFamilyRecord =
  components["schemas"]["QuestionFamilyRecord"];
export type CoverageGapRecord = components["schemas"]["CoverageGapRecord"];
export type QuestionFreshnessRecord =
  components["schemas"]["QuestionFreshnessRecord"];
export type LicenseInventoryRecord =
  components["schemas"]["LicenseInventoryRecord"];
export type ProvenanceInventoryRecord =
  components["schemas"]["ProvenanceInventoryRecord"];

const apiUrl = process.env.NEXT_PUBLIC_RIGOR_API_URL ?? "http://localhost:8002";

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

async function requestJson<T>(
  path: string,
  options: {
    method?: string;
    body?: unknown;
    signal?: AbortSignal;
    headers?: Record<string, string>;
    form?: FormData;
  } = {},
): Promise<T> {
  const accessToken =
    typeof window === "undefined" || typeof window.localStorage === "undefined"
      ? null
      : window.localStorage.getItem("rigor.auth.access-token");
  const response = await fetch(`${apiUrl}${path}`, {
    method: options.method ?? "GET",
    headers: {
      Accept: "application/json",
      ...(options.body ? { "Content-Type": "application/json" } : {}),
      ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
      ...options.headers,
    },
    ...(options.body ? { body: JSON.stringify(options.body) } : {}),
    ...(options.form ? { body: options.form } : {}),
    ...(options.signal ? { signal: options.signal } : {}),
  });
  if (!response.ok) {
    if (response.status === 401 && typeof window !== "undefined")
      window.dispatchEvent(new Event("rigor:unauthorized"));
    throw new ApiError(
      response.status,
      `Rigor API returned ${response.status}`,
    );
  }
  return (await response.json()) as T;
}

export function getContentStats(signal?: AbortSignal) {
  return requestJson<ContentStats>(
    "/api/v1/content/stats",
    signal ? { signal } : {},
  );
}

export function getManifestQuestions(
  filters: {
    query: string;
    track: string;
    difficulty: string;
    page?: number;
    pageSize?: number;
  },
  signal?: AbortSignal,
) {
  const params = new URLSearchParams({
    page: String(filters.page ?? 1),
    page_size: String(filters.pageSize ?? 18),
  });
  if (filters.query) params.set("query", filters.query);
  if (filters.track) params.set("track", filters.track);
  if (filters.difficulty) params.set("difficulty", filters.difficulty);
  return requestJson<QuestionPage>(
    `/api/v1/manifest/questions?${params.toString()}`,
    signal ? { signal } : {},
  );
}

export function getManifestQuestion(slug: string, signal?: AbortSignal) {
  return requestJson<ManifestQuestion>(
    `/api/v1/manifest/questions/${encodeURIComponent(slug)}`,
    signal ? { signal } : {},
  );
}

export function getPublishedQuestions(
  filters: {
    query: string;
    track: string;
    skill: string;
    difficulty: string;
    role: string;
    companyStyle: string;
    completionStatus: string;
    sort: string;
    page?: number;
    pageSize?: number;
  },
  signal?: AbortSignal,
) {
  const params = new URLSearchParams({
    page: String(filters.page ?? 1),
    page_size: String(filters.pageSize ?? 18),
    sort: filters.sort,
  });
  if (filters.query) params.set("query", filters.query);
  if (filters.track) params.set("track", filters.track);
  if (filters.skill) params.set("skill", filters.skill);
  if (filters.difficulty) params.set("difficulty", filters.difficulty);
  if (filters.role) params.set("role", filters.role);
  if (filters.companyStyle) params.set("company_style", filters.companyStyle);
  if (filters.completionStatus)
    params.set("completion_status", filters.completionStatus);
  return requestJson<CatalogQuestionPage>(
    `/api/v1/questions?${params.toString()}`,
    signal ? { signal } : {},
  );
}

export function getPublishedQuestion(slug: string, signal?: AbortSignal) {
  return requestJson<CandidateQuestionDetail>(
    `/api/v1/questions/${encodeURIComponent(slug)}`,
    signal ? { signal } : {},
  );
}

export function getProfile(signal?: AbortSignal) {
  return requestJson<CandidateProfile>(
    "/api/v1/profile",
    signal ? { signal } : {},
  );
}

export function putProfile(profile: CandidateProfileInput) {
  return requestJson<CandidateProfile>("/api/v1/profile", {
    method: "PUT",
    body: profile,
  });
}

export function getReviewQueue(signal?: AbortSignal) {
  return requestJson<ReviewQueueItem[]>(
    "/api/v1/reviews",
    signal ? { signal } : {},
  );
}

export function assignReviewer(
  questionVersionId: string,
  kind: ReviewKind,
  reviewerSubjectId: string,
) {
  return requestJson<ReviewActionResult>(
    `/api/v1/reviews/${questionVersionId}/assignment`,
    {
      method: "PUT",
      body: { kind, reviewer_subject_id: reviewerSubjectId },
    },
  );
}

export function decideReview(
  questionVersionId: string,
  kind: ReviewKind,
  outcome: ReviewOutcome,
  reason: string,
) {
  return requestJson<ReviewActionResult>(
    `/api/v1/reviews/${questionVersionId}/${kind}-decision`,
    { method: "POST", body: { outcome, reason } },
  );
}

export function publishQuestion(questionVersionId: string) {
  return requestJson<ReviewActionResult>(
    `/api/v1/reviews/${questionVersionId}/publish`,
    {
      method: "POST",
      headers: { "Idempotency-Key": `publish-${questionVersionId}` },
    },
  );
}

export function transitionQuestion(
  questionVersionId: string,
  target: "deprecated" | "archived",
) {
  return requestJson<ReviewActionResult>(
    `/api/v1/reviews/${questionVersionId}/transition/${target}`,
    { method: "POST" },
  );
}

export function getContinuousCoverage(signal?: AbortSignal) {
  return requestJson<ContinuousCoverageStats>(
    "/api/v1/admin/coverage",
    signal ? { signal } : {},
  );
}

export function getCompetencyCoverage(signal?: AbortSignal) {
  return requestJson<CompetencyCoverage[]>(
    "/api/v1/admin/coverage/competencies",
    signal ? { signal } : {},
  );
}

export function getSources(
  filters: { connectorStatus?: string; coverageLevel?: string } = {},
  signal?: AbortSignal,
) {
  const params = new URLSearchParams();
  if (filters.connectorStatus)
    params.set("connector_status", filters.connectorStatus);
  if (filters.coverageLevel)
    params.set("coverage_level", filters.coverageLevel);
  const query = params.size ? `?${params.toString()}` : "";
  return requestJson<SourceRegistryRecord[]>(
    `/api/v1/admin/sources${query}`,
    signal ? { signal } : {},
  );
}

export function registerSource(source: SourceRegistryInput) {
  return requestJson<SourceRegistryRecord>("/api/v1/admin/sources", {
    method: "POST",
    body: source,
  });
}

export function reviewSource(sourceId: string, review: SourceReviewInput) {
  return requestJson<SourceRegistryRecord>(
    `/api/v1/admin/sources/${sourceId}/review`,
    { method: "PUT", body: review },
  );
}

export function verifySource(sourceId: string) {
  return requestJson<SourceSyncResult>(
    `/api/v1/admin/sources/${sourceId}/sync`,
    {
      method: "POST",
      body: {
        sync_mode: "verification",
        references: [],
        complete_snapshot: false,
      },
    },
  );
}

export function getExternalReferences(
  filters: {
    query?: string;
    sourceId?: string;
    difficulty?: string;
    competency?: string;
    page?: number;
    pageSize?: number;
  },
  signal?: AbortSignal,
) {
  const params = new URLSearchParams({
    page: String(filters.page ?? 1),
    page_size: String(filters.pageSize ?? 24),
  });
  if (filters.query) params.set("query", filters.query);
  if (filters.sourceId) params.set("source_id", filters.sourceId);
  if (filters.difficulty) params.set("difficulty", filters.difficulty);
  if (filters.competency) params.set("competency", filters.competency);
  return requestJson<ExternalReferencePage>(
    `/api/v1/external-references?${params.toString()}`,
    signal ? { signal } : {},
  );
}

export function getExternalReferenceFacets(signal?: AbortSignal) {
  return requestJson<ExternalReferenceFacets>(
    "/api/v1/external-reference-facets",
    signal ? { signal } : {},
  );
}

export function getPracticeSummary(signal?: AbortSignal) {
  return requestJson<PracticeCatalogSummary>(
    "/api/v1/practice/summary",
    signal ? { signal } : {},
  );
}

export function getCatalogStatus(signal?: AbortSignal) {
  return requestJson<CatalogSourceStatus[]>(
    "/api/v1/admin/catalog/status",
    signal ? { signal } : {},
  );
}

export function runApprovedCollectors() {
  return requestJson<{
    status: "completed";
    external_references: number;
    completed_at: string;
  }>("/api/v1/admin/catalog/collect", { method: "POST" });
}

export function getContentImports(signal?: AbortSignal) {
  return requestJson<ContentImportSummary[]>(
    "/api/v1/admin/content/imports",
    signal ? { signal } : {},
  );
}

export function uploadContentImport(
  file: File,
  options: { dryRun: boolean; visibility: "public" | "private" },
) {
  const form = new FormData();
  form.set("file", file);
  form.set("dry_run", String(options.dryRun));
  form.set("visibility", options.visibility);
  return requestJson<ContentImportReport>("/api/v1/admin/content/imports", {
    method: "POST",
    form,
  });
}

export function rollbackContentImport(importId: string) {
  return requestJson<{
    import_id: string;
    status: "rolled_back";
    rolled_back_versions: number;
  }>(`/api/v1/admin/content/imports/${importId}/rollback`, { method: "POST" });
}

export function runContentFactoryBatch(batch: ContentFactoryBatchInput) {
  return requestJson<ContentImportReport>(
    "/api/v1/admin/content/factory/batches",
    { method: "POST", body: batch },
  );
}

export type QuestionIntelligenceMode =
  | "questions"
  | "families"
  | "variants"
  | "gaps"
  | "duplicates"
  | "freshness"
  | "licenses"
  | "provenance";

export function getQuestionIntelligence(
  mode: QuestionIntelligenceMode,
  signal?: AbortSignal,
) {
  const endpoint =
    mode === "variants" ? "" : `/${mode === "questions" ? "" : mode}`;
  return requestJson<
    | AdminQuestionRecord[]
    | DuplicateCandidateRecord[]
    | QuestionFamilyRecord[]
    | CoverageGapRecord[]
    | QuestionFreshnessRecord[]
    | LicenseInventoryRecord[]
    | ProvenanceInventoryRecord[]
  >(`/api/v1/admin/questions${endpoint}`, signal ? { signal } : {}).then(
    (items) =>
      mode === "variants"
        ? (items as AdminQuestionRecord[]).filter(
            (item) => item.record_type === "question_variation",
          )
        : items,
  );
}

export function recomputeCoverageGaps() {
  return requestJson<{ created_count: number; open_gap_count: number }>(
    "/api/v1/admin/questions/gaps/recompute",
    { method: "POST" },
  );
}
