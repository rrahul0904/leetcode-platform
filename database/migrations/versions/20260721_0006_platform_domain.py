"""Add the shared candidate activity domain and enforce tenant isolation.

Revision ID: 20260721_0006
Revises: 20260720_0005
Create Date: 2026-07-21
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260721_0006"
down_revision: str | None = "20260720_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PRACTICE_STATES = (
    "CREATED",
    "IN_PROGRESS",
    "PAUSED",
    "SUBMITTED",
    "EVALUATING",
    "COMPLETED",
    "ABANDONED",
)
EXECUTION_STATES = (
    "QUEUED",
    "RUNNING",
    "PASSED",
    "FAILED",
    "ERROR",
    "CANCELLED",
    "TIMED_OUT",
)
SIMULATION_STATES = (
    "CONFIGURING",
    "ACTIVE",
    "REQUIREMENT_CHANGE",
    "FAILURE_INJECTED",
    "SUBMITTED",
    "EVALUATING",
    "COMPLETED",
    "ABANDONED",
)
MOCK_INTERVIEW_STATES = (
    "CREATED",
    "READY",
    "IN_PROGRESS",
    "PAUSED",
    "COMPLETED",
    "CANCELLED",
)


def enum(name: str, values: tuple[str, ...]) -> postgresql.ENUM:
    return postgresql.ENUM(*values, name=name, create_type=False)


practice_state = enum("practice_session_state", PRACTICE_STATES)
execution_state = enum("execution_state", EXECUTION_STATES)
simulation_state = enum("simulation_state", SIMULATION_STATES)
mock_interview_state = enum("mock_interview_state", MOCK_INTERVIEW_STATES)


def id_column() -> sa.Column[sa.Uuid]:
    return sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()"))


def organization_column() -> sa.Column[sa.Uuid]:
    return sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("organizations.id"))


def candidate_column() -> sa.Column[sa.Uuid]:
    return sa.Column(
        "candidate_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )


def created_at() -> sa.Column[sa.DateTime]:
    return sa.Column(
        "created_at",
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.text("CURRENT_TIMESTAMP"),
    )


def updated_at() -> sa.Column[sa.DateTime]:
    return sa.Column(
        "updated_at",
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.text("CURRENT_TIMESTAMP"),
    )


def json_object(name: str, *, nullable: bool = False) -> sa.Column[postgresql.JSONB]:
    return sa.Column(name, postgresql.JSONB(), nullable=nullable, server_default="{}")


def json_array(name: str, *, nullable: bool = False) -> sa.Column[postgresql.JSONB]:
    return sa.Column(name, postgresql.JSONB(), nullable=nullable, server_default="[]")


def direct_policy(table: str) -> None:
    op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"""
        CREATE POLICY {table}_principal_isolation ON {table}
        USING (
          (session_user = 'rigor_migrator'
            AND current_setting('rigor.maintenance_bypass', true) = 'on')
          OR (
            candidate_id::text = NULLIF(current_setting('rigor.user_id', true), '')
            AND (
              organization_id IS NULL
              OR organization_id::text =
                   NULLIF(current_setting('rigor.organization_id', true), '')
            )
          )
        )
        WITH CHECK (
          (session_user = 'rigor_migrator'
            AND current_setting('rigor.maintenance_bypass', true) = 'on')
          OR (
            candidate_id::text = NULLIF(current_setting('rigor.user_id', true), '')
            AND (
              organization_id IS NULL
              OR organization_id::text =
                   NULLIF(current_setting('rigor.organization_id', true), '')
            )
          )
        )
        """
    )


def child_policy(table: str, parent: str, foreign_key: str) -> None:
    op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"""
        CREATE POLICY {table}_principal_isolation ON {table}
        USING (
          (session_user = 'rigor_migrator'
            AND current_setting('rigor.maintenance_bypass', true) = 'on')
          OR EXISTS (SELECT 1 FROM {parent} p WHERE p.id = {table}.{foreign_key})
        )
        WITH CHECK (
          (session_user = 'rigor_migrator'
            AND current_setting('rigor.maintenance_bypass', true) = 'on')
          OR EXISTS (SELECT 1 FROM {parent} p WHERE p.id = {table}.{foreign_key})
        )
        """
    )


def upgrade() -> None:
    bind = op.get_bind()
    practice_state.create(bind)
    execution_state.create(bind)
    simulation_state.create(bind)
    mock_interview_state.create(bind)

    op.create_table(
        "practice_sessions",
        id_column(),
        organization_column(),
        candidate_column(),
        sa.Column("question_version_id", sa.Uuid(), sa.ForeignKey("question_versions.id")),
        sa.Column("session_type", sa.String(40), nullable=False, server_default="HOSTED_QUESTION"),
        sa.Column("state", practice_state, nullable=False, server_default="CREATED"),
        sa.Column("runtime", sa.String(60)),
        sa.Column("elapsed_seconds", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("hint_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("paused_at", sa.DateTime(timezone=True)),
        sa.Column("submitted_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        created_at(),
        updated_at(),
        sa.CheckConstraint("elapsed_seconds >= 0 AND hint_count >= 0", name="ck_practice_metrics"),
    )
    op.create_index(
        "ix_practice_sessions_candidate_state",
        "practice_sessions",
        ["candidate_id", "state", sa.text("updated_at DESC")],
    )
    op.create_index(
        "ix_practice_sessions_question",
        "practice_sessions",
        ["question_version_id", "candidate_id"],
    )
    op.create_table(
        "practice_session_events",
        id_column(),
        sa.Column(
            "session_id",
            sa.Uuid(),
            sa.ForeignKey("practice_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("sequence_number", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(80), nullable=False),
        json_object("payload"),
        created_at(),
        sa.UniqueConstraint("session_id", "sequence_number", name="uq_practice_event_sequence"),
    )
    op.create_table(
        "practice_artifacts",
        id_column(),
        sa.Column(
            "session_id",
            sa.Uuid(),
            sa.ForeignKey("practice_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("artifact_type", sa.String(60), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        json_object("content"),
        sa.Column("content_hash", sa.String(64), nullable=False),
        created_at(),
        sa.UniqueConstraint(
            "session_id", "artifact_type", "version", name="uq_practice_artifact_version"
        ),
        sa.CheckConstraint("version > 0", name="ck_practice_artifact_version"),
    )
    op.create_table(
        "editor_drafts",
        id_column(),
        organization_column(),
        candidate_column(),
        sa.Column("question_version_id", sa.Uuid(), sa.ForeignKey("question_versions.id")),
        sa.Column("runtime", sa.String(60), nullable=False),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("source_hash", sa.String(64), nullable=False),
        created_at(),
        updated_at(),
        sa.UniqueConstraint(
            "candidate_id", "question_version_id", "runtime", name="uq_editor_draft_target"
        ),
        sa.CheckConstraint("revision > 0", name="ck_editor_draft_revision"),
    )

    op.add_column("submissions", organization_column())
    op.add_column(
        "submissions",
        sa.Column("practice_session_id", sa.Uuid(), sa.ForeignKey("practice_sessions.id")),
    )
    op.add_column("submissions", sa.Column("idempotency_key", sa.String(160)))
    op.create_unique_constraint(
        "uq_submissions_candidate_idempotency", "submissions", ["candidate_id", "idempotency_key"]
    )
    op.create_table(
        "submission_results",
        id_column(),
        sa.Column(
            "submission_id",
            sa.Uuid(),
            sa.ForeignKey("submissions.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("status", execution_state, nullable=False),
        sa.Column("public_results", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("hidden_total", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("hidden_passed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("runtime_ms", sa.Integer()),
        sa.Column("memory_kb", sa.Integer()),
        sa.Column("error_category", sa.String(80)),
        sa.Column("candidate_message", sa.Text()),
        json_object("quality_signals"),
        created_at(),
        sa.CheckConstraint(
            "hidden_total >= 0 AND hidden_passed BETWEEN 0 AND hidden_total",
            name="ck_submission_hidden_summary",
        ),
    )
    op.create_table(
        "execution_requests",
        id_column(),
        organization_column(),
        candidate_column(),
        sa.Column("practice_session_id", sa.Uuid(), sa.ForeignKey("practice_sessions.id")),
        sa.Column("submission_id", sa.Uuid(), sa.ForeignKey("submissions.id")),
        sa.Column("question_version_id", sa.Uuid(), sa.ForeignKey("question_versions.id")),
        sa.Column("runtime", sa.String(60), nullable=False),
        sa.Column("adapter", sa.String(60), nullable=False),
        sa.Column("state", execution_state, nullable=False, server_default="QUEUED"),
        sa.Column("idempotency_key", sa.String(160), nullable=False),
        sa.Column("source_hash", sa.String(64), nullable=False),
        sa.Column("limits", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column(
            "queued_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        created_at(),
        sa.UniqueConstraint("candidate_id", "idempotency_key", name="uq_execution_idempotency"),
    )
    op.create_index(
        "ix_execution_requests_candidate_state",
        "execution_requests",
        ["candidate_id", "state", sa.text("created_at DESC")],
    )
    op.create_table(
        "execution_events",
        id_column(),
        sa.Column(
            "execution_request_id",
            sa.Uuid(),
            sa.ForeignKey("execution_requests.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("sequence_number", sa.Integer(), nullable=False),
        sa.Column("state", execution_state, nullable=False),
        json_object("details"),
        created_at(),
        sa.UniqueConstraint(
            "execution_request_id", "sequence_number", name="uq_execution_event_sequence"
        ),
    )

    op.create_table(
        "learning_plans",
        id_column(),
        organization_column(),
        candidate_column(),
        sa.Column("target_role", sa.String(160), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="ACTIVE"),
        sa.Column("starts_on", sa.Date(), nullable=False),
        sa.Column("ends_on", sa.Date()),
        sa.Column("weekly_minutes", sa.Integer(), nullable=False),
        sa.Column("generation_version", sa.String(80), nullable=False),
        json_object("rationale"),
        created_at(),
        updated_at(),
        sa.CheckConstraint("weekly_minutes > 0", name="ck_learning_plan_minutes"),
    )
    op.create_index(
        "ix_learning_plans_candidate_status", "learning_plans", ["candidate_id", "status"]
    )
    op.create_table(
        "learning_plan_activities",
        id_column(),
        sa.Column(
            "learning_plan_id",
            sa.Uuid(),
            sa.ForeignKey("learning_plans.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("activity_type", sa.String(60), nullable=False),
        sa.Column("source_type", sa.String(60), nullable=False),
        sa.Column("source_id", sa.String(255), nullable=False),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="PLANNED"),
        sa.Column("due_at", sa.DateTime(timezone=True)),
        sa.Column("estimated_minutes", sa.Integer(), nullable=False),
        sa.Column("sequence_number", sa.Integer(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        json_object("metadata"),
        created_at(),
        updated_at(),
        sa.UniqueConstraint(
            "learning_plan_id", "sequence_number", name="uq_learning_activity_sequence"
        ),
        sa.CheckConstraint("estimated_minutes > 0", name="ck_learning_activity_minutes"),
    )
    op.create_index(
        "ix_learning_activities_due",
        "learning_plan_activities",
        ["status", "due_at"],
    )
    op.create_table(
        "candidate_competency_evidence",
        id_column(),
        organization_column(),
        candidate_column(),
        sa.Column("competency_id", sa.Uuid(), sa.ForeignKey("competencies.id"), nullable=False),
        sa.Column("source_type", sa.String(60), nullable=False),
        sa.Column("source_id", sa.String(255), nullable=False),
        sa.Column("score", sa.Numeric(6, 5), nullable=False),
        sa.Column("confidence", sa.Numeric(6, 5), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        json_object("evidence"),
        created_at(),
        sa.UniqueConstraint(
            "candidate_id",
            "source_type",
            "source_id",
            "competency_id",
            name="uq_competency_evidence",
        ),
        sa.CheckConstraint("score BETWEEN 0 AND 1", name="ck_competency_evidence_score"),
        sa.CheckConstraint("confidence BETWEEN 0 AND 1", name="ck_competency_evidence_confidence"),
    )
    op.create_index(
        "ix_competency_evidence_candidate_observed",
        "candidate_competency_evidence",
        ["candidate_id", sa.text("observed_at DESC")],
    )
    op.create_table(
        "candidate_competency_mastery",
        id_column(),
        organization_column(),
        candidate_column(),
        sa.Column("competency_id", sa.Uuid(), sa.ForeignKey("competencies.id"), nullable=False),
        sa.Column("mastery", sa.Numeric(6, 5), nullable=False),
        sa.Column("confidence", sa.Numeric(6, 5), nullable=False),
        sa.Column("evidence_count", sa.Integer(), nullable=False),
        sa.Column("last_evidence_at", sa.DateTime(timezone=True)),
        sa.Column("calculation_version", sa.String(80), nullable=False),
        created_at(),
        updated_at(),
        sa.UniqueConstraint("candidate_id", "competency_id", name="uq_candidate_mastery"),
        sa.CheckConstraint("mastery BETWEEN 0 AND 1", name="ck_candidate_mastery_score"),
        sa.CheckConstraint("confidence BETWEEN 0 AND 1", name="ck_candidate_mastery_confidence"),
        sa.CheckConstraint("evidence_count >= 0", name="ck_candidate_mastery_evidence_count"),
    )

    op.create_table(
        "assessment_sessions",
        id_column(),
        organization_column(),
        candidate_column(),
        sa.Column("status", sa.String(30), nullable=False, server_default="CREATED"),
        sa.Column("target_role", sa.String(160), nullable=False),
        sa.Column("seniority", sa.String(40), nullable=False),
        json_object("configuration"),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        created_at(),
        updated_at(),
    )
    op.create_index(
        "ix_assessment_candidate_status", "assessment_sessions", ["candidate_id", "status"]
    )
    op.create_table(
        "assessment_results",
        id_column(),
        sa.Column(
            "assessment_session_id",
            sa.Uuid(),
            sa.ForeignKey("assessment_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("item_type", sa.String(60), nullable=False),
        sa.Column("item_id", sa.String(255), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("score", sa.Numeric(6, 5), nullable=False),
        sa.Column("confidence", sa.Numeric(6, 5), nullable=False),
        sa.Column("time_seconds", sa.Integer(), nullable=False),
        sa.Column("hint_count", sa.Integer(), nullable=False, server_default="0"),
        json_object("answer"),
        json_object("remediation"),
        created_at(),
        sa.UniqueConstraint(
            "assessment_session_id",
            "item_type",
            "item_id",
            "attempt_number",
            name="uq_assessment_attempt",
        ),
        sa.CheckConstraint("score BETWEEN 0 AND 1", name="ck_assessment_score"),
        sa.CheckConstraint("confidence BETWEEN 0 AND 1", name="ck_assessment_confidence"),
    )

    op.create_table(
        "simulation_sessions",
        id_column(),
        organization_column(),
        candidate_column(),
        sa.Column("case_slug", sa.String(180), nullable=False),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("status", simulation_state, nullable=False, server_default="CONFIGURING"),
        sa.Column("current_event_index", sa.Integer(), nullable=False, server_default="0"),
        json_object("current_requirements"),
        json_object("capacity_inputs"),
        json_object("capacity_results"),
        json_array("rubric_evidence"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("submitted_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        created_at(),
        updated_at(),
        sa.CheckConstraint(
            "current_event_index >= 0 AND version > 0", name="ck_simulation_position"
        ),
    )
    op.create_index(
        "ix_simulation_candidate_status",
        "simulation_sessions",
        ["candidate_id", "status", sa.text("updated_at DESC")],
    )
    op.create_table(
        "simulation_events",
        id_column(),
        sa.Column(
            "session_id",
            sa.Uuid(),
            sa.ForeignKey("simulation_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("sequence_number", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(80), nullable=False),
        json_object("payload"),
        sa.Column("candidate_response", sa.Text()),
        json_array("affected_component_ids"),
        json_object("evidence"),
        created_at(),
        sa.Column("responded_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("session_id", "sequence_number", name="uq_simulation_event_sequence"),
    )
    op.create_table(
        "simulation_artifacts",
        id_column(),
        sa.Column(
            "session_id",
            sa.Uuid(),
            sa.ForeignKey("simulation_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("artifact_type", sa.String(60), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        json_object("content"),
        created_at(),
        sa.UniqueConstraint(
            "session_id", "artifact_type", "version", name="uq_simulation_artifact_version"
        ),
        sa.CheckConstraint("version > 0", name="ck_simulation_artifact_version"),
    )

    op.create_table(
        "mock_interview_sessions",
        id_column(),
        organization_column(),
        candidate_column(),
        sa.Column("interview_type", sa.String(60), nullable=False),
        sa.Column("target_role", sa.String(160), nullable=False),
        sa.Column("source_type", sa.String(60), nullable=False),
        sa.Column("source_id", sa.String(255), nullable=False),
        sa.Column("status", mock_interview_state, nullable=False, server_default="CREATED"),
        sa.Column("current_phase", sa.String(60), nullable=False, server_default="INTRODUCTION"),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        created_at(),
        updated_at(),
    )
    op.create_index(
        "ix_mock_interview_candidate_status",
        "mock_interview_sessions",
        ["candidate_id", "status", sa.text("updated_at DESC")],
    )
    op.create_table(
        "mock_interview_messages",
        id_column(),
        sa.Column(
            "session_id",
            sa.Uuid(),
            sa.ForeignKey("mock_interview_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("sequence_number", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(30), nullable=False),
        sa.Column("phase", sa.String(60), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        json_object("evidence"),
        created_at(),
        sa.UniqueConstraint("session_id", "sequence_number", name="uq_mock_message_sequence"),
    )
    op.create_table(
        "mock_interview_reports",
        id_column(),
        sa.Column(
            "session_id",
            sa.Uuid(),
            sa.ForeignKey("mock_interview_sessions.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("overall_score", sa.Numeric(6, 5), nullable=False),
        json_array("rubric_evidence"),
        json_array("strengths"),
        json_array("growth_areas"),
        json_array("next_steps"),
        created_at(),
        sa.CheckConstraint("overall_score BETWEEN 0 AND 1", name="ck_mock_report_score"),
    )

    op.create_table(
        "ai_interactions",
        id_column(),
        organization_column(),
        candidate_column(),
        sa.Column("practice_session_id", sa.Uuid(), sa.ForeignKey("practice_sessions.id")),
        sa.Column(
            "mock_interview_session_id", sa.Uuid(), sa.ForeignKey("mock_interview_sessions.id")
        ),
        sa.Column("simulation_session_id", sa.Uuid(), sa.ForeignKey("simulation_sessions.id")),
        sa.Column("mode", sa.String(40), nullable=False),
        sa.Column("phase", sa.String(60), nullable=False),
        sa.Column("provider", sa.String(120), nullable=False),
        sa.Column("model_identifier", sa.String(160), nullable=False),
        sa.Column("prompt_version", sa.String(80), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("response_hash", sa.String(64), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=False),
        json_object("token_usage"),
        json_object("cost_metadata"),
        sa.Column("safety_outcome", sa.String(60), nullable=False),
        sa.Column("redaction_outcome", sa.String(60), nullable=False),
        json_object("state"),
        created_at(),
        sa.CheckConstraint("latency_ms >= 0", name="ck_ai_interaction_latency"),
    )
    op.create_index(
        "ix_ai_interactions_candidate_created",
        "ai_interactions",
        ["candidate_id", sa.text("created_at DESC")],
    )
    op.create_table(
        "ai_evidence",
        id_column(),
        sa.Column(
            "ai_interaction_id",
            sa.Uuid(),
            sa.ForeignKey("ai_interactions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("competency_id", sa.Uuid(), sa.ForeignKey("competencies.id")),
        sa.Column("evidence_type", sa.String(80), nullable=False),
        sa.Column("claim", sa.Text(), nullable=False),
        sa.Column("score", sa.Numeric(6, 5)),
        sa.Column("confidence", sa.Numeric(6, 5), nullable=False),
        json_object("supporting_data"),
        created_at(),
        sa.CheckConstraint("score IS NULL OR score BETWEEN 0 AND 1", name="ck_ai_evidence_score"),
        sa.CheckConstraint("confidence BETWEEN 0 AND 1", name="ck_ai_evidence_confidence"),
    )

    op.create_table(
        "readiness_snapshots",
        id_column(),
        organization_column(),
        candidate_column(),
        sa.Column("overall_readiness", sa.Numeric(6, 5), nullable=False),
        sa.Column("confidence", sa.Numeric(6, 5), nullable=False),
        sa.Column("evidence_count", sa.Integer(), nullable=False),
        json_object("competency_readiness"),
        json_object("role_readiness"),
        json_object("company_style_readiness"),
        json_array("current_risks"),
        json_array("recommended_actions"),
        sa.Column("calculation_version", sa.String(80), nullable=False),
        sa.Column("calculated_at", sa.DateTime(timezone=True), nullable=False),
        created_at(),
        sa.CheckConstraint("overall_readiness BETWEEN 0 AND 1", name="ck_readiness_score"),
        sa.CheckConstraint("confidence BETWEEN 0 AND 1", name="ck_readiness_confidence"),
        sa.CheckConstraint("evidence_count >= 0", name="ck_readiness_evidence_count"),
    )
    op.create_index(
        "ix_readiness_candidate_calculated",
        "readiness_snapshots",
        ["candidate_id", sa.text("calculated_at DESC")],
    )
    op.create_table(
        "recommendation_events",
        id_column(),
        organization_column(),
        candidate_column(),
        sa.Column("recommendation_type", sa.String(60), nullable=False),
        sa.Column("source_type", sa.String(60), nullable=False),
        sa.Column("source_id", sa.String(255), nullable=False),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="SHOWN"),
        sa.Column("recommended_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("acted_at", sa.DateTime(timezone=True)),
        json_object("context"),
        created_at(),
        sa.CheckConstraint("rank > 0", name="ck_recommendation_rank"),
    )
    op.create_index(
        "ix_recommendation_candidate_status",
        "recommendation_events",
        ["candidate_id", "status", sa.text("recommended_at DESC")],
    )

    for table in (
        "practice_sessions",
        "editor_drafts",
        "submissions",
        "execution_requests",
        "learning_plans",
        "candidate_competency_evidence",
        "candidate_competency_mastery",
        "assessment_sessions",
        "simulation_sessions",
        "mock_interview_sessions",
        "ai_interactions",
        "readiness_snapshots",
        "recommendation_events",
    ):
        direct_policy(table)
    for table, parent, foreign_key in (
        ("practice_session_events", "practice_sessions", "session_id"),
        ("practice_artifacts", "practice_sessions", "session_id"),
        ("submission_results", "submissions", "submission_id"),
        ("execution_events", "execution_requests", "execution_request_id"),
        ("learning_plan_activities", "learning_plans", "learning_plan_id"),
        ("assessment_results", "assessment_sessions", "assessment_session_id"),
        ("simulation_events", "simulation_sessions", "session_id"),
        ("simulation_artifacts", "simulation_sessions", "session_id"),
        ("mock_interview_messages", "mock_interview_sessions", "session_id"),
        ("mock_interview_reports", "mock_interview_sessions", "session_id"),
        ("ai_evidence", "ai_interactions", "ai_interaction_id"),
    ):
        child_policy(table, parent, foreign_key)

    op.execute("ALTER TABLE questions FORCE ROW LEVEL SECURITY")
    op.execute("DROP POLICY IF EXISTS questions_tenant_isolation ON questions")
    op.execute(
        """
        CREATE POLICY questions_tenant_isolation ON questions
        USING (
          visibility = 'public'
          OR (session_user = 'rigor_migrator'
              AND current_setting('rigor.maintenance_bypass', true) = 'on')
          OR (
            organization_id::text = NULLIF(current_setting('rigor.organization_id', true), '')
            AND (
              owner_user_id IS NULL
              OR owner_user_id::text = NULLIF(current_setting('rigor.user_id', true), '')
            )
          )
        )
        WITH CHECK (
          (session_user = 'rigor_migrator'
            AND current_setting('rigor.maintenance_bypass', true) = 'on')
          OR (
            organization_id::text = NULLIF(current_setting('rigor.organization_id', true), '')
            AND owner_user_id::text = NULLIF(current_setting('rigor.user_id', true), '')
          )
        )
        """
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS questions_tenant_isolation ON questions")
    op.execute("ALTER TABLE questions NO FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY questions_tenant_isolation ON questions
        USING (
            visibility = 'public'
            OR organization_id::text = NULLIF(current_setting('rigor.organization_id', true), '')
            OR current_setting('rigor.bypass_rls', true) = 'on'
        )
        WITH CHECK (
            visibility = 'public'
            OR organization_id::text = NULLIF(current_setting('rigor.organization_id', true), '')
            OR current_setting('rigor.bypass_rls', true) = 'on'
        )
        """
    )

    child_tables = (
        "ai_evidence",
        "mock_interview_reports",
        "mock_interview_messages",
        "simulation_artifacts",
        "simulation_events",
        "assessment_results",
        "learning_plan_activities",
        "execution_events",
        "submission_results",
        "practice_artifacts",
        "practice_session_events",
    )
    direct_tables = (
        "recommendation_events",
        "readiness_snapshots",
        "ai_interactions",
        "mock_interview_sessions",
        "simulation_sessions",
        "assessment_sessions",
        "candidate_competency_mastery",
        "candidate_competency_evidence",
        "learning_plans",
        "execution_requests",
        "submissions",
        "editor_drafts",
        "practice_sessions",
    )
    for table in (*child_tables, *direct_tables):
        op.execute(f"DROP POLICY IF EXISTS {table}_principal_isolation ON {table}")

    for table in (
        "recommendation_events",
        "readiness_snapshots",
        "ai_evidence",
        "ai_interactions",
        "mock_interview_reports",
        "mock_interview_messages",
        "mock_interview_sessions",
        "simulation_artifacts",
        "simulation_events",
        "simulation_sessions",
        "assessment_results",
        "assessment_sessions",
        "candidate_competency_mastery",
        "candidate_competency_evidence",
        "learning_plan_activities",
        "learning_plans",
        "execution_events",
        "execution_requests",
        "submission_results",
    ):
        op.drop_table(table)
    op.drop_constraint("uq_submissions_candidate_idempotency", "submissions", type_="unique")
    op.drop_column("submissions", "idempotency_key")
    op.drop_column("submissions", "practice_session_id")
    op.drop_column("submissions", "organization_id")
    op.drop_table("editor_drafts")
    op.drop_table("practice_artifacts")
    op.drop_table("practice_session_events")
    op.drop_table("practice_sessions")

    mock_interview_state.drop(op.get_bind())
    simulation_state.drop(op.get_bind())
    execution_state.drop(op.get_bind())
    practice_state.drop(op.get_bind())
