from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import Field, TypeAdapter, model_validator

from .models import (
    CompanyStyleTag,
    ComplexityAnalysis,
    Difficulty,
    DimensionProfile,
    Hint,
    NonEmptyText,
    Rubric,
    StrictModel,
    TestCase,
)


class QuestionType(StrEnum):
    PYTHON_CODING = "python_coding"
    SQL_CODING = "sql_coding"
    DATA_MODELING = "data_modeling"
    DATA_ARCHITECTURE = "data_architecture"
    DISTRIBUTED_SYSTEMS = "distributed_systems"
    SYSTEM_DESIGN = "system_design"
    ML_SYSTEM_DESIGN = "ml_system_design"
    GENAI_ARCHITECTURE = "genai_architecture"
    AI_INFRASTRUCTURE = "ai_infrastructure"
    AI_AGENTS = "ai_agents"
    AI_EVALUATION = "ai_evaluation"
    AI_SAFETY = "ai_safety"
    BEHAVIORAL = "behavioral"
    TECHNICAL_LEADERSHIP = "technical_leadership"
    STAFF_PRINCIPAL_CASE = "staff_principal_case"


class PublicationStatus(StrEnum):
    DRAFT = "draft"
    GENERATED = "generated"
    IMPORTED = "imported"
    VALIDATION_FAILED = "validation_failed"
    DUPLICATE_REVIEW_REQUIRED = "duplicate_review_required"
    AWAITING_TECHNICAL_REVIEW = "awaiting_technical_review"
    TECHNICAL_CHANGES_REQUESTED = "technical_changes_requested"
    AWAITING_EDITORIAL_REVIEW = "awaiting_editorial_review"
    EDITORIAL_CHANGES_REQUESTED = "editorial_changes_requested"
    APPROVED = "approved"
    PUBLISHED = "published"
    DEPRECATED = "deprecated"
    ARCHIVED = "archived"
    REJECTED_FOR_RIGHTS_RISK = "rejected_for_rights_risk"


class RightsBasis(StrEnum):
    ORIGINAL = "original"
    ORGANIZATION_OWNED = "organization_owned"
    LICENSED = "licensed"


class AuthorAttribution(StrictModel):
    id: NonEmptyText
    display_name: NonEmptyText
    organization: str | None = None


class ReviewerAttribution(StrictModel):
    subject_id: NonEmptyText
    kind: Literal["technical", "editorial", "originality", "rights"]
    decision: Literal["pending", "approved", "changes_requested", "rejected"] = "pending"
    decided_at: datetime | None = None


class ContentLicense(StrictModel):
    rights_basis: RightsBasis
    license_identifier: NonEmptyText
    certification: NonEmptyText
    evidence: list[NonEmptyText] = Field(min_length=1)
    provider: str | None = None
    agreement_identifier: str | None = None
    permitted_territories: list[NonEmptyText] = Field(default_factory=list)
    attribution_requirements: list[NonEmptyText] = Field(default_factory=list)
    modification_rights: bool = True
    export_rights: bool = True
    ai_training_rights: bool = False
    expiration_date: date | None = None
    retention_requirements: list[NonEmptyText] = Field(default_factory=list)
    deletion_requirements: list[NonEmptyText] = Field(default_factory=list)

    @model_validator(mode="after")
    def licensed_content_has_agreement(self) -> ContentLicense:
        if self.rights_basis == RightsBasis.LICENSED and (
            not self.provider or not self.agreement_identifier
        ):
            raise ValueError("licensed content requires provider and agreement_identifier")
        return self


class UniversalProvenance(StrictModel):
    originality_statement: NonEmptyText
    authoring_method: NonEmptyText
    source_classes: list[NonEmptyText]
    source_notes: list[NonEmptyText]
    source_content_hash: Annotated[str, Field(pattern=r"^sha256:[0-9a-f]{64}$")]
    certification_evidence: list[NonEmptyText] = Field(min_length=1)
    source_uri: str | None = None


class UniversalAlternative(StrictModel):
    name: NonEmptyText
    content: NonEmptyText
    advantages: list[NonEmptyText]
    disadvantages: list[NonEmptyText]


class UniversalSolution(StrictModel):
    content: NonEmptyText
    explanation: NonEmptyText
    complexity: ComplexityAnalysis | None = None
    alternatives: list[UniversalAlternative]
    trade_offs: list[NonEmptyText] = Field(default_factory=list)
    debugging_notes: list[NonEmptyText] = Field(default_factory=list)


class PythonDetails(StrictModel):
    runtime: Literal["3.13"] = "3.13"
    input_specification: NonEmptyText
    output_specification: NonEmptyText
    starter_code: NonEmptyText
    tests: list[TestCase] = Field(min_length=2)
    time_limit_ms: int = Field(gt=0, le=30_000)
    memory_limit_mb: int = Field(gt=0, le=2048)
    expected_complexity: ComplexityAnalysis
    production_variation: NonEmptyText

    @model_validator(mode="after")
    def public_and_hidden_tests_exist(self) -> PythonDetails:
        public_count = sum(test.visibility == "public" for test in self.tests)
        hidden_count = sum(test.visibility == "hidden" for test in self.tests)
        if public_count < 3 or hidden_count < 1:
            raise ValueError("Python questions require at least three public and one hidden test")
        return self


class SqlDetails(StrictModel):
    dialect: Literal["postgresql18"] = "postgresql18"
    business_scenario: NonEmptyText
    schema_diagram_description: NonEmptyText
    ddl: NonEmptyText
    seed_sql: NonEmptyText
    expected_output_columns: list[NonEmptyText]
    tests: list[TestCase] = Field(min_length=2)
    reference_sql: NonEmptyText
    suggested_indexes: list[NonEmptyText]
    execution_plan_discussion: NonEmptyText
    statement_timeout_ms: int = Field(gt=0, le=30_000)

    @model_validator(mode="after")
    def public_and_hidden_tests_exist(self) -> SqlDetails:
        visibility = {test.visibility for test in self.tests}
        if "public" not in visibility or "hidden" not in visibility:
            raise ValueError("SQL questions require public and hidden tests")
        return self


class ArchitectureNode(StrictModel):
    id: NonEmptyText
    label: NonEmptyText
    kind: NonEmptyText
    group: str | None = None


class ArchitectureEdge(StrictModel):
    source: NonEmptyText
    target: NonEmptyText
    label: NonEmptyText
    protocol: str | None = None


class ArchitectureGraph(StrictModel):
    nodes: list[ArchitectureNode] = Field(min_length=2)
    edges: list[ArchitectureEdge] = Field(min_length=1)
    groups: list[NonEmptyText] = Field(default_factory=list)
    trust_boundaries: list[NonEmptyText] = Field(default_factory=list)
    data_flows: list[NonEmptyText] = Field(min_length=1)
    failure_domains: list[NonEmptyText] = Field(min_length=1)
    annotations: list[NonEmptyText] = Field(default_factory=list)


class ArchitectureDetails(StrictModel):
    interviewer_only_context: NonEmptyText
    functional_requirements: list[NonEmptyText] = Field(min_length=1)
    non_functional_requirements: list[NonEmptyText] = Field(min_length=1)
    out_of_scope: list[NonEmptyText]
    scale_assumptions: list[NonEmptyText] = Field(min_length=1)
    capacity_calculation: NonEmptyText
    api_design: list[NonEmptyText]
    data_model: list[NonEmptyText]
    architecture: ArchitectureGraph
    architecture_explanation: NonEmptyText
    request_data_flow: list[NonEmptyText]
    storage_analysis: NonEmptyText
    partition_strategy: NonEmptyText
    cache_strategy: NonEmptyText
    consistency_model: NonEmptyText
    reliability_plan: NonEmptyText
    failure_scenarios: list[NonEmptyText] = Field(min_length=1)
    disaster_recovery: NonEmptyText
    multi_region_strategy: NonEmptyText
    security: list[NonEmptyText]
    privacy: list[NonEmptyText]
    abuse_prevention: list[NonEmptyText]
    observability: list[NonEmptyText]
    deployment: NonEmptyText
    cost_considerations: list[NonEmptyText]
    build_versus_buy: NonEmptyText
    migration_plan: NonEmptyText
    alternative_designs: list[NonEmptyText]
    trade_offs: list[NonEmptyText]
    interview_follow_up_tree: dict[str, list[NonEmptyText]]
    requirement_changes: list[NonEmptyText]


class BehavioralDetails(StrictModel):
    competency: NonEmptyText
    context_expectations: list[NonEmptyText]
    evidence_checklist: list[NonEmptyText]
    follow_up_probes: list[NonEmptyText]
    staff_expectations: list[NonEmptyText]
    principal_expectations: list[NonEmptyText]


class UniversalQuestionBase(StrictModel):
    id: Annotated[str, Field(pattern=r"^[A-Z]+-[0-9]{4}$")]
    version: Annotated[str, Field(pattern=r"^[0-9]+\.[0-9]+\.[0-9]+$")]
    title: NonEmptyText
    slug: Annotated[str, Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")]
    primary_track: NonEmptyText
    secondary_skills: list[NonEmptyText]
    difficulty: Difficulty
    difficulty_dimensions: DimensionProfile
    role_level: Literal["senior", "staff", "principal"]
    company_style_tags: list[CompanyStyleTag]
    learning_objectives: list[NonEmptyText] = Field(min_length=1)
    prerequisites: list[NonEmptyText]
    estimated_duration_minutes: int = Field(ge=15, le=240)
    public_problem_statement: NonEmptyText
    candidate_instructions: list[NonEmptyText] = Field(min_length=1)
    interviewer_instructions: list[NonEmptyText] = Field(min_length=1)
    constraints: list[NonEmptyText]
    assumptions: list[NonEmptyText]
    expected_clarifying_questions: list[NonEmptyText]
    hints: list[Hint]
    rubric: Rubric
    reference_solution: UniversalSolution
    alternative_solutions: list[UniversalAlternative]
    common_mistakes: list[NonEmptyText]
    follow_up_questions: list[NonEmptyText]
    easier_variants: list[NonEmptyText]
    harder_variants: list[NonEmptyText]
    related_question_ids: list[str]
    author: AuthorAttribution
    reviewers: list[ReviewerAttribution]
    license: ContentLicense
    provenance: UniversalProvenance
    source_content_hash: Annotated[str, Field(pattern=r"^sha256:[0-9a-f]{64}$")]
    created_at: datetime
    updated_at: datetime
    publication_status: PublicationStatus

    @model_validator(mode="after")
    def hashes_match(self) -> UniversalQuestionBase:
        if self.source_content_hash != self.provenance.source_content_hash:
            raise ValueError("source_content_hash must match provenance source_content_hash")
        return self


class PythonCodingQuestion(UniversalQuestionBase):
    question_type: Literal[QuestionType.PYTHON_CODING]
    type_specification: PythonDetails


class SqlCodingQuestion(UniversalQuestionBase):
    question_type: Literal[QuestionType.SQL_CODING]
    type_specification: SqlDetails


ArchitectureQuestionType = Literal[
    QuestionType.DATA_MODELING,
    QuestionType.DATA_ARCHITECTURE,
    QuestionType.DISTRIBUTED_SYSTEMS,
    QuestionType.SYSTEM_DESIGN,
    QuestionType.ML_SYSTEM_DESIGN,
    QuestionType.GENAI_ARCHITECTURE,
    QuestionType.AI_INFRASTRUCTURE,
    QuestionType.AI_AGENTS,
    QuestionType.AI_EVALUATION,
    QuestionType.AI_SAFETY,
    QuestionType.STAFF_PRINCIPAL_CASE,
]


class ArchitectureQuestion(UniversalQuestionBase):
    question_type: ArchitectureQuestionType
    type_specification: ArchitectureDetails


class BehavioralQuestion(UniversalQuestionBase):
    question_type: Literal[QuestionType.BEHAVIORAL, QuestionType.TECHNICAL_LEADERSHIP]
    type_specification: BehavioralDetails


type UniversalQuestion = Annotated[
    PythonCodingQuestion | SqlCodingQuestion | ArchitectureQuestion | BehavioralQuestion,
    Field(discriminator="question_type"),
]
universal_question_adapter: TypeAdapter[UniversalQuestion] = TypeAdapter(UniversalQuestion)
