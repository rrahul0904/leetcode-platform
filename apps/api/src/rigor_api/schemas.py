from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator
from rigor_question_schema.universal import UniversalQuestion


class ApiModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class FieldError(ApiModel):
    field: str
    message: str


class ErrorResponse(ApiModel):
    code: str
    message: str
    correlation_id: str
    field_errors: list[FieldError] = []
    retryable: bool = False


class HealthResponse(ApiModel):
    status: str
    service: str = "rigor-api"


class ManifestQuestion(ApiModel):
    id: str
    working_title: str
    slug: str
    primary_track: str
    skills: list[str]
    difficulty: str
    role_level: str
    company_style_tags: list[str]
    learning_objective: str
    estimated_duration_minutes: int
    content_status: str
    originality_status: str
    difficulty_calibration: str


class Page[T](ApiModel):
    items: list[T]
    page: int
    page_size: int
    total: int
    has_next: bool


class ContentStats(ApiModel):
    growth_model: Literal["continuous_unbounded"] = "continuous_unbounded"
    foundation_manifest_entries: int
    planned_questions: int
    complete_questions: int
    validated_questions: int
    published_questions: int
    track_counts: dict[str, int]
    difficulty_counts: dict[str, int]
    disclaimer: str


class Role(StrEnum):
    candidate = "candidate"
    content_author = "content-author"
    technical_reviewer = "technical-reviewer"
    editorial_reviewer = "editorial-reviewer"
    platform_administrator = "platform-administrator"


class AuthenticatedPrincipal(ApiModel):
    subject_id: str
    email: str
    display_name: str
    organization_id: str | None = None
    roles: list[Role]
    permissions: list[str]
    authentication_provider: str
    token_issued_at: datetime
    correlation_id: str


class LocalTokenExchange(ApiModel):
    grant_type: str
    code: str
    client_id: str
    redirect_uri: str
    code_verifier: str


class OIDCTokenResponse(ApiModel):
    access_token: str
    id_token: str
    token_type: str = "Bearer"
    expires_in: int
    scope: str = "openid email profile"


class ExperienceLevel(StrEnum):
    mid = "mid"
    senior = "senior"
    staff = "staff"
    principal = "principal"
    manager = "manager"


class PreferredProgrammingLanguage(StrEnum):
    python = "python"
    sql = "sql"
    mixed = "mixed"


class PreparationIntensity(StrEnum):
    steady = "steady"
    focused = "focused"
    intensive = "intensive"


class CandidateProfileInput(ApiModel):
    target_roles: list[str] = Field(min_length=1, max_length=5)
    target_companies: list[str] = Field(default_factory=list, max_length=10)
    experience_level: ExperienceLevel
    preferred_programming_language: PreferredProgrammingLanguage
    weekly_study_hours: int = Field(ge=1, le=40)
    interview_date: date | None = None
    strong_areas: list[str] = Field(default_factory=list, max_length=12)
    weak_areas: list[str] = Field(default_factory=list, max_length=12)
    preparation_intensity: PreparationIntensity

    @field_validator("target_roles", "target_companies", "strong_areas", "weak_areas")
    @classmethod
    def normalize_list(cls, values: list[str]) -> list[str]:
        normalized = [value.strip() for value in values if value.strip()]
        unique = list(dict.fromkeys(normalized))
        if len(unique) != len(normalized):
            raise ValueError("values must be unique")
        return unique


class CandidateProfile(CandidateProfileInput):
    subject_id: str
    email: str
    display_name: str
    completion_state: str = "complete"
    completed_at: datetime
    updated_at: datetime


class PublicExample(ApiModel):
    id: str
    name: str
    input: object
    expected_output: object | None = None


class CatalogQuestion(ApiModel):
    external_id: str
    title: str
    slug: str
    track: str
    skills: list[str]
    difficulty: str
    role_level: str
    estimated_duration_minutes: int
    learning_objectives: list[str]
    company_style_tags: list[str]
    publication_version: str
    completion_status: str = "not_started"


class CandidateQuestionDetail(CatalogQuestion):
    prerequisites: list[str]
    problem_statement: str
    candidate_instructions: list[str]
    public_constraints: list[str]
    public_examples: list[PublicExample]
    starter_code: str | None = None


class ContentState(StrEnum):
    draft = "draft"
    generated = "generated"
    automated_validation_failed = "automated_validation_failed"
    awaiting_technical_review = "awaiting_technical_review"
    awaiting_editorial_review = "awaiting_editorial_review"
    approved = "approved"
    published = "published"
    deprecated = "deprecated"
    archived = "archived"


class ReviewKind(StrEnum):
    technical = "technical"
    editorial = "editorial"


class ReviewOutcome(StrEnum):
    approved = "approved"
    changes_requested = "changes_requested"
    rejected = "rejected"


class ReviewAssignmentInput(ApiModel):
    kind: ReviewKind
    reviewer_subject_id: str = Field(min_length=3, max_length=255)


class ReviewDecisionInput(ApiModel):
    outcome: ReviewOutcome
    reason: str = Field(min_length=10, max_length=4000)


class ReviewAssignmentSummary(ApiModel):
    kind: ReviewKind
    reviewer_subject_id: str
    reviewer_display_name: str
    completed_at: datetime | None


class ReviewQueueItem(ApiModel):
    question_version_id: UUID
    external_id: str
    slug: str
    title: str
    version: str
    state: ContentState
    author_subject_id: str
    validation_status: str | None
    assignments: list[ReviewAssignmentSummary]


class ReviewActionResult(ApiModel):
    question_version_id: UUID
    state: ContentState
    message: str


class SubmissionRuntime(StrEnum):
    python = "python3.13"
    postgresql = "postgresql18"


class SubmissionStatus(StrEnum):
    queued = "queued"
    running = "running"
    passed = "passed"
    failed = "failed"
    error = "error"


class SubmissionInput(ApiModel):
    runtime: SubmissionRuntime
    submitted_source: str = Field(min_length=1, max_length=100_000)


class PublicTestResult(ApiModel):
    id: str
    name: str
    passed: bool
    expected_output: object | None = None
    actual_output: object | None = None


class HiddenTestSummary(ApiModel):
    total: int = Field(ge=0)
    passed: int = Field(ge=0)


class Submission(ApiModel):
    id: UUID
    question_slug: str
    question_title: str
    publication_version: str
    runtime: SubmissionRuntime
    submitted_source: str
    status: SubmissionStatus
    public_test_results: list[PublicTestResult]
    hidden_test_summary: HiddenTestSummary
    error_category: str | None
    execution_duration_ms: int | None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None


class ImportStageResult(ApiModel):
    stage: str
    status: str
    findings: list[str]
    metrics: dict[str, object]


class ContentImportItem(ApiModel):
    ordinal: int
    source_path: str
    external_id: str | None
    slug: str | None
    status: str
    errors: list[str]
    warnings: list[str]
    normalized_hash: str | None
    similarity_score: float | None
    question_version_id: UUID | None
    stages: list[ImportStageResult]


class ContentImportReport(ApiModel):
    import_id: UUID
    source_filename: str
    source_method: str
    status: str
    dry_run: bool
    question_count: int
    accepted_count: int
    rejected_count: int
    warning_count: int
    rollback_available: bool
    started_at: datetime
    completed_at: datetime | None
    items: list[ContentImportItem]


class ContentImportSummary(ApiModel):
    import_id: UUID
    source_filename: str
    source_method: str
    status: str
    dry_run: bool
    question_count: int
    accepted_count: int
    rejected_count: int
    warning_count: int
    rollback_available: bool
    started_at: datetime
    completed_at: datetime | None


class ImportErrorItem(ApiModel):
    ordinal: int
    source_path: str
    external_id: str | None
    errors: list[str]


class ImportRollbackResult(ApiModel):
    import_id: UUID
    status: Literal["rolled_back"] = "rolled_back"
    rolled_back_versions: int


class ContentFactoryBatchInput(ApiModel):
    questions: list[UniversalQuestion] = Field(min_length=1, max_length=10)
    prompt_version: str = Field(min_length=3, max_length=80)
    model_provider: str = Field(min_length=2, max_length=120)
    model_identifier: str = Field(min_length=2, max_length=160)
    allow_mixed_tracks: bool = False
    dry_run: bool = True


class AdminQuestionRecord(ApiModel):
    question_id: UUID
    external_id: str
    slug: str
    record_type: str
    visibility: str
    version_id: UUID
    version: str
    title: str
    primary_track: str
    difficulty: str
    role_level: str
    state: str
    source_revision: str
    updated_at: datetime
    is_current_published: bool


class DuplicateCandidateRecord(ApiModel):
    duplicate_id: UUID
    imported_external_id: str | None
    imported_slug: str | None
    existing_question_version_id: UUID | None
    existing_title: str | None
    similarity_score: float
    suggested_action: str
    manual_reviewer_flag: bool
    dimension_scores: dict[str, float]
    created_at: datetime


class QuestionFamilyRecord(ApiModel):
    family_id: UUID
    slug: str
    name: str
    canonical_competency: str | None
    core_problem_structure: str
    variation_dimensions: list[str]
    member_count: int
    updated_at: datetime


class CoverageGapRecord(ApiModel):
    gap_id: UUID
    competency_slug: str
    competency_name: str
    role_level: str
    difficulty: str
    hosted_count: int
    external_reference_count: int
    recommended_question_count: int
    recommended_action: str
    status: str
    created_at: datetime


class GapRecomputeResult(ApiModel):
    created_count: int
    open_gap_count: int


class QuestionFreshnessRecord(ApiModel):
    question_id: UUID
    external_id: str
    title: str
    state: str
    updated_at: datetime
    age_days: int
    freshness_status: Literal["current", "review_due", "stale"]


class LicenseInventoryRecord(ApiModel):
    question_version_id: UUID
    external_id: str
    title: str
    rights_basis: str
    license_identifier: str
    provider: str | None
    expiration_date: date | None
    created_at: datetime


class ProvenanceInventoryRecord(ApiModel):
    question_version_id: UUID
    external_id: str
    title: str
    authoring_method: str
    originality_statement: str
    source_notes: list[str]
    created_at: datetime


class CoverageLevel(StrEnum):
    blocked = "BLOCKED"
    discovery_only = "DISCOVERY_ONLY"
    deeplink_only = "DEEPLINK_ONLY"
    metadata_only = "METADATA_ONLY"
    abstract_signal_only = "ABSTRACT_SIGNAL_ONLY"
    user_private_import = "USER_PRIVATE_IMPORT"
    open_license_full_content = "OPEN_LICENSE_FULL_CONTENT"
    partner_licensed_full_content = "PARTNER_LICENSED_FULL_CONTENT"
    enterprise_owned_full_content = "ENTERPRISE_OWNED_FULL_CONTENT"
    platform_original_full_content = "PLATFORM_ORIGINAL_FULL_CONTENT"


class SourceRightsStatus(StrEnum):
    unreviewed = "unreviewed"
    blocked = "blocked"
    metadata_permitted = "metadata_permitted"
    open_license_verified = "open_license_verified"
    partner_license_verified = "partner_license_verified"
    enterprise_owned_verified = "enterprise_owned_verified"
    platform_original = "platform_original"


class ConnectorStatus(StrEnum):
    unreviewed = "unreviewed"
    approved = "approved"
    paused = "paused"
    disabled = "disabled"
    failing = "failing"


class SourceRegistryInput(ApiModel):
    source_name: str = Field(min_length=2, max_length=240)
    canonical_domain: str = Field(min_length=3, max_length=255)
    source_category: str = Field(min_length=2, max_length=80)
    discovery_method: str = Field(min_length=2, max_length=80)
    access_method: str = Field(default="manual_review", min_length=2, max_length=80)
    estimated_content_volume: int | None = Field(default=None, ge=0)
    priority: int = Field(default=50, ge=0, le=100)


class SourceReviewInput(ApiModel):
    rights_status: SourceRightsStatus
    coverage_level: CoverageLevel
    collection_mode: str = Field(min_length=2, max_length=60)
    connector_status: ConnectorStatus
    connector_type: str | None = Field(default=None, max_length=120)
    connector_configuration: dict[str, object] = Field(default_factory=dict)
    next_scheduled_sync: datetime | None = None
    review_notes: str = Field(min_length=10, max_length=4000)


class SourceRegistryRecord(ApiModel):
    source_id: UUID
    source_name: str
    canonical_domain: str
    source_category: str
    discovery_method: str
    discovered_at: datetime
    last_reviewed_at: datetime | None
    reviewed_by: UUID | None
    access_method: str
    rights_status: SourceRightsStatus
    coverage_level: CoverageLevel
    collection_mode: str
    connector_status: ConnectorStatus
    estimated_content_volume: int | None
    actual_indexed_volume: int
    last_successful_sync: datetime | None
    next_scheduled_sync: datetime | None
    failure_count: int
    priority: int
    connector_type: str | None
    connector_configuration: dict[str, object]
    pause_reason: str | None
    created_at: datetime
    updated_at: datetime


class ExternalReferenceInput(ApiModel):
    source_external_id: str | None = Field(default=None, max_length=255)
    canonical_url: str = Field(min_length=8, max_length=2000)
    title: str | None = Field(default=None, max_length=500)
    abstract: str | None = Field(default=None, max_length=5000)
    difficulty: str | None = Field(default=None, max_length=40)
    topic_metadata: list[str] = Field(default_factory=list, max_length=100)
    patterns: list[str] = Field(default_factory=list, max_length=40)
    competency_slugs: list[str] = Field(default_factory=list, max_length=40)
    source_metadata: dict[str, object] = Field(default_factory=dict)
    source_availability: Literal["available", "unavailable", "deleted", "unknown"] = "available"
    access_tier: Literal["public", "account_required", "premium", "unknown"] = "public"
    technology_freshness: Literal["stable", "current", "fast_moving", "stale"] = "stable"


class SourceSyncInput(ApiModel):
    sync_mode: Literal["initial_backfill", "incremental", "verification"]
    cursor_before: dict[str, object] | None = None
    cursor_after: dict[str, object] | None = None
    references: list[ExternalReferenceInput] = Field(max_length=1000)
    complete_snapshot: bool = False


class SourceSyncResult(ApiModel):
    sync_id: UUID
    source_id: UUID
    status: Literal["completed"] = "completed"
    discovered_count: int
    created_count: int
    updated_count: int
    unavailable_count: int
    completed_at: datetime


class ExternalReference(ApiModel):
    reference_id: UUID
    source_id: UUID
    source_name: str
    canonical_domain: str
    coverage_level: CoverageLevel
    canonical_url: str
    title: str | None
    abstract: str | None
    difficulty: str | None
    topic_metadata: list[str]
    patterns: list[str]
    competency_slugs: list[str]
    source_availability: str
    access_tier: str
    technology_freshness: str
    first_seen_at: datetime
    last_seen_at: datetime
    last_verified_at: datetime | None
    review_due_at: datetime | None


class CatalogFilterOption(ApiModel):
    value: str
    label: str
    count: int


class ExternalReferenceFacets(ApiModel):
    sources: list[CatalogFilterOption]
    difficulties: list[CatalogFilterOption]
    competencies: list[CatalogFilterOption]


class PracticeSourceCount(ApiModel):
    source_id: UUID
    source_name: str
    reference_count: int


class PracticeCatalogSummary(ApiModel):
    external_references: int
    hosted_records: int
    awaiting_review: int
    published_hosted_questions: int
    approved_sources: int
    last_successful_collection: datetime | None
    source_counts: list[PracticeSourceCount]


class CatalogSourceStatus(ApiModel):
    source_id: UUID
    source_name: str
    canonical_domain: str
    connector_status: str
    last_run: datetime | None
    references_collected: int
    references_updated: int
    failures: int
    rights_status: str
    coverage_level: str
    last_error: str | None
    next_available_action: str


class CatalogCollectionRunResult(ApiModel):
    status: Literal["completed"] = "completed"
    external_references: int
    completed_at: datetime


class ContinuousCoverageStats(ApiModel):
    growth_model: Literal["continuous_unbounded"] = "continuous_unbounded"
    foundation_manifest_entries: int
    discovered_sources: int
    approved_sources: int
    blocked_sources: int
    planned_questions: int
    external_references: int
    hosted_original_questions: int
    hosted_licensed_questions: int
    open_license_questions: int
    schema_complete_questions: int
    executable_validated_questions: int
    technically_reviewed_questions: int
    editorially_reviewed_questions: int
    published_questions: int
    question_families: int
    meaningful_variants: int
    user_private_questions: int
    enterprise_private_questions: int
    deprecated_questions: int
    unavailable_external_references: int
    open_coverage_gaps: int
    last_synchronization_time: datetime | None


class CompetencyCoverage(ApiModel):
    competency_id: UUID
    slug: str
    name: str
    parent_slug: str | None
    hosted_question_count: int
    external_reference_count: int
    published_question_count: int
    coverage_score: float
    last_updated_at: datetime


PageNumber = Annotated[int, Field(ge=1)]
PageSize = Annotated[int, Field(ge=1, le=100)]
