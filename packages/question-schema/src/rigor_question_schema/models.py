from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

NonEmptyText = Annotated[str, Field(min_length=1)]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Difficulty(StrEnum):
    FOUNDATIONAL = "foundational"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"
    STAFF = "staff"
    PRINCIPAL = "principal"


class ReviewStatus(StrEnum):
    DRAFT = "draft"
    GENERATED = "generated"
    AUTOMATED_VALIDATION_FAILED = "automated_validation_failed"
    AWAITING_TECHNICAL_REVIEW = "awaiting_technical_review"
    AWAITING_EDITORIAL_REVIEW = "awaiting_editorial_review"
    APPROVED = "approved"
    PUBLISHED = "published"
    DEPRECATED = "deprecated"
    ARCHIVED = "archived"


class DimensionProfile(StrictModel):
    conceptual: int = Field(ge=1, le=5)
    implementation: int = Field(ge=1, le=5)
    scale: int = Field(ge=1, le=5)
    ambiguity: int = Field(ge=1, le=5)
    prerequisite_depth: int = Field(ge=1, le=5)


class CompanyStyleTag(StrictModel):
    slug: NonEmptyText
    relevance_rationale: NonEmptyText
    public_theme_sources: list[Annotated[str, Field(pattern=r"^https://")]] = Field(
        default_factory=list
    )
    disclaimer: Literal["independent-content"] = "independent-content"


class RubricDimension(StrictModel):
    name: NonEmptyText
    description: NonEmptyText
    weight: int = Field(gt=0, le=100)
    evidence_required: list[NonEmptyText]
    strong_indicators: list[NonEmptyText]
    weak_indicators: list[NonEmptyText]


class Rubric(StrictModel):
    dimensions: list[RubricDimension] = Field(min_length=1)
    score_bands: dict[str, NonEmptyText]

    @model_validator(mode="after")
    def weights_total_one_hundred(self) -> Rubric:
        total = sum(dimension.weight for dimension in self.dimensions)
        if total != 100:
            raise ValueError(f"rubric weights must total 100, received {total}")
        return self


class Hint(StrictModel):
    reveal_level: int = Field(ge=1, le=5)
    text: NonEmptyText
    penalty_points: int = Field(ge=0, le=100)


class Provenance(StrictModel):
    originality_statement: NonEmptyText
    authoring_method: NonEmptyText
    source_classes: list[NonEmptyText]
    source_notes: list[NonEmptyText]
    content_hash: NonEmptyText
    authored_at: datetime
    author_id: NonEmptyText


class ValidationSummary(StrictModel):
    schema_valid: bool = False
    references_valid: bool = False
    executable_tests_passed: bool | None = None
    duplicate_check_passed: bool = False
    rubric_check_passed: bool = False
    last_run_id: str | None = None


class TestCase(StrictModel):
    id: NonEmptyText
    name: NonEmptyText
    visibility: Literal["public", "hidden", "edge", "property"]
    input: object
    expected_output: object | None = None
    property_name: str | None = None
    comparison: str | dict[str, object] | None = None


class PythonSpecification(StrictModel):
    runtime: Literal["3.11", "3.12", "3.13", "3.14"]
    input_specification: NonEmptyText
    output_specification: NonEmptyText
    starter_code: NonEmptyText
    tests: list[TestCase] = Field(min_length=1)
    time_limit_ms: int = Field(gt=0)
    memory_limit_mb: int = Field(gt=0)


class SqlSpecification(StrictModel):
    dialect: Literal["postgresql"] = "postgresql"
    business_problem: NonEmptyText
    ddl: NonEmptyText
    seed_data: NonEmptyText
    expected_result: list[dict[str, object]]
    tests: list[TestCase] = Field(min_length=1)
    statement_timeout_ms: int = Field(gt=0)


class ArchitectureSpecification(StrictModel):
    functional_requirements: list[NonEmptyText]
    non_functional_requirements: list[NonEmptyText]
    scale_assumptions: list[NonEmptyText]
    capacity_estimation_example: NonEmptyText
    expected_artifacts: list[NonEmptyText]
    failure_scenarios: list[NonEmptyText]
    requirement_changes: list[NonEmptyText]


class BehavioralSpecification(StrictModel):
    competency: NonEmptyText
    follow_up_probes: list[NonEmptyText]
    evidence_checklist: list[NonEmptyText]
    staff_expectations: list[NonEmptyText]
    principal_expectations: list[NonEmptyText]


QuestionMode = (
    PythonSpecification | SqlSpecification | ArchitectureSpecification | BehavioralSpecification
)


class QuestionPackage(StrictModel):
    id: Annotated[str, Field(pattern=r"^[A-Z]+-[0-9]{4}$")]
    title: NonEmptyText
    slug: Annotated[str, Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")]
    primary_track: NonEmptyText
    secondary_skills: list[NonEmptyText]
    role_families: list[NonEmptyText]
    expected_seniority: Literal["senior", "staff", "principal"]
    difficulty: Difficulty
    difficulty_dimensions: DimensionProfile
    company_style_tags: list[CompanyStyleTag]
    learning_objectives: list[NonEmptyText]
    prerequisites: list[NonEmptyText]
    estimated_duration_minutes: int = Field(ge=15, le=240)
    problem_statement: NonEmptyText
    candidate_instructions: list[NonEmptyText]
    interviewer_instructions: list[NonEmptyText]
    constraints: list[NonEmptyText]
    assumptions: list[NonEmptyText]
    expected_clarifying_questions: list[NonEmptyText]
    evaluation_rubric: Rubric
    hints: list[Hint]
    common_mistakes: list[NonEmptyText]
    strong_answer_indicators: list[NonEmptyText]
    weak_answer_indicators: list[NonEmptyText]
    follow_up_questions: list[NonEmptyText]
    harder_variants: list[NonEmptyText]
    easier_variants: list[NonEmptyText]
    related_question_ids: list[str]
    mode_specification: QuestionMode
    provenance: Provenance
    version: Annotated[str, Field(pattern=r"^[0-9]+\.[0-9]+\.[0-9]+$")]
    review_status: ReviewStatus
    validation: ValidationSummary


class ComplexityAnalysis(StrictModel):
    expected_time: NonEmptyText
    expected_space: NonEmptyText
    explanation: NonEmptyText


class AlternativeApproach(StrictModel):
    name: NonEmptyText
    solution: NonEmptyText
    advantages: list[NonEmptyText]
    disadvantages: list[NonEmptyText]


class SolutionPackage(StrictModel):
    question_id: NonEmptyText
    question_version: NonEmptyText
    reference_solution: NonEmptyText
    explanation: NonEmptyText
    alternatives: list[AlternativeApproach]
    trade_off_analysis: list[NonEmptyText]
    complexity: ComplexityAnalysis | None = None
    testing_and_debugging: list[NonEmptyText]
    production_follow_ups: list[NonEmptyText]
    critical_omissions: list[NonEmptyText]
    strong_response_example: NonEmptyText
    interviewer_follow_up_tree: dict[str, list[NonEmptyText]]
    source_content_hash: NonEmptyText
