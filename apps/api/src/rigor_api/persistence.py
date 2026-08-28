from __future__ import annotations

import json
from typing import Any
from uuid import UUID

from sqlalchemy import Connection, Engine, text

from .schemas import AuthenticatedPrincipal, CatalogAggregateSummary, PlatformStatistics


def ensure_user(connection: Connection, principal: AuthenticatedPrincipal) -> UUID:
    """Persist identity metadata without mutating application authorization.

    Normal authenticated requests may refresh trusted identity metadata and last-login
    timestamps, but PostgreSQL ``user_roles`` remains authoritative and is never
    rewritten here. Role provisioning belongs to explicit trusted provisioning paths
    (Clerk webhook/reconciliation) or the controlled local-development bootstrap.
    """

    user_id = connection.execute(
        text(
            """
            INSERT INTO users (
                identity_subject, email, display_name, email_verified, last_login_at
            ) VALUES (
                :subject, :email, :display_name, true, CURRENT_TIMESTAMP
            )
            ON CONFLICT (identity_subject) DO UPDATE SET
                email = EXCLUDED.email,
                display_name = EXCLUDED.display_name,
                email_verified = true,
                last_login_at = CURRENT_TIMESTAMP,
                updated_at = CURRENT_TIMESTAMP
            RETURNING id
            """
        ),
        {
            "subject": principal.subject_id,
            "email": principal.email,
            "display_name": principal.display_name,
        },
    ).scalar_one()
    return UUID(str(user_id))


def synchronize_local_user_roles(
    connection: Connection,
    principal: AuthenticatedPrincipal,
    user_id: UUID,
) -> None:
    """Synchronize roles only for the controlled local OIDC development provider."""

    if principal.authentication_provider != "local-oidc":
        raise ValueError("Only the controlled local OIDC provider may synchronize request roles")
    connection.execute(
        text("DELETE FROM user_roles WHERE user_id = :user_id"), {"user_id": user_id}
    )
    for role in principal.roles:
        connection.execute(
            text("INSERT INTO user_roles (user_id, role_slug) VALUES (:user_id, :role)"),
            {"user_id": user_id, "role": role.value},
        )


def audit_event(
    connection: Connection,
    principal: AuthenticatedPrincipal,
    actor_user_id: UUID,
    *,
    action: str,
    resource_type: str,
    resource_id: str,
    details: dict[str, Any],
) -> None:
    connection.execute(
        text(
            """
            INSERT INTO audit_events (
                actor_user_id, action, resource_type, resource_id, details, correlation_id
            ) VALUES (
                :actor_user_id, :action, :resource_type, :resource_id,
                CAST(:details AS jsonb), :correlation_id
            )
            """
        ),
        {
            "actor_user_id": actor_user_id,
            "action": action,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "details": json.dumps(details),
            "correlation_id": principal.correlation_id,
        },
    )


class PlatformStatisticsRepository:
    """PostgreSQL is the only source for operational product counters."""

    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def statistics(self) -> PlatformStatistics:
        with self._engine.connect() as connection:
            row = (
                connection.execute(
                    text(
                        """
                    SELECT
                      (SELECT count(*) FROM questions
                       WHERE record_type IN (
                         'platform_original_hosted_question', 'licensed_hosted_question',
                         'open_license_hosted_question', 'question_variation',
                         'practice_drill', 'mock_interview_case',
                         'staff_principal_case_study')) AS hosted_questions,
                      (SELECT count(*) FROM questions q
                       JOIN question_versions v ON v.id=q.current_published_version_id
                       WHERE v.state='published'::content_state) AS published_hosted_questions,
                      (SELECT count(*) FROM external_question_references) AS external_references,
                      (SELECT count(*) FROM practice_sessions) AS practice_sessions,
                      (SELECT count(*) FROM submissions) AS submissions,
                      (SELECT count(*) FROM simulation_sessions
                       WHERE status='COMPLETED'::simulation_state) AS completed_simulations,
                      (SELECT count(*) FROM mock_interview_sessions
                       WHERE status='COMPLETED'::mock_interview_state)
                        AS completed_mock_interviews,
                      (SELECT count(*) FROM learning_plan_activities) AS learning_activities,
                      (SELECT count(*) FROM candidate_competency_evidence)
                        AS competency_evidence,
                      (SELECT count(DISTINCT u.id) FROM users u
                       JOIN user_roles ur ON ur.user_id=u.id AND ur.role_slug='candidate'
                       WHERE u.deleted_at IS NULL
                         AND u.last_login_at >= CURRENT_TIMESTAMP - INTERVAL '30 days')
                        AS active_candidates
                    """
                    )
                )
                .mappings()
                .one()
            )
        return PlatformStatistics.model_validate(dict(row))

    def catalog_summary(self) -> CatalogAggregateSummary:
        with self._engine.connect() as connection:
            row = (
                connection.execute(
                    text(
                        """
                    SELECT
                      (SELECT count(*) FROM questions
                       WHERE record_type IN (
                         'platform_original_hosted_question', 'licensed_hosted_question',
                         'open_license_hosted_question', 'question_variation',
                         'practice_drill', 'mock_interview_case',
                         'staff_principal_case_study')) AS hosted_count,
                      (SELECT count(*) FROM questions q
                       JOIN question_versions v ON v.id=q.current_published_version_id
                       WHERE v.state='published'::content_state) AS published_count,
                      (SELECT count(*) FROM external_question_references) AS external_count,
                      (SELECT count(*) FROM source_registry) AS source_count,
                      (SELECT max(completed_at) FROM source_sync_runs
                       WHERE status='completed') AS last_collection,
                      (SELECT count(*) FROM content_imports WHERE status='failed')
                        AS import_failures,
                      (SELECT count(*) FROM question_versions
                       WHERE state IN ('awaiting_technical_review'::content_state,
                                       'awaiting_editorial_review'::content_state))
                        AS review_backlog,
                      (SELECT count(*) FROM simulation_sessions) AS simulation_count,
                      (SELECT count(*) FROM mock_interview_sessions) AS mock_interview_count
                    """
                    )
                )
                .mappings()
                .one()
            )
            track_rows = connection.execute(
                text(
                    """
                    SELECT t.slug, count(q.id) AS count
                    FROM question_tracks t
                    LEFT JOIN questions q ON q.primary_track_id=t.id
                    GROUP BY t.slug ORDER BY t.slug
                    """
                )
            ).all()
            difficulty_rows = connection.execute(
                text(
                    """
                    SELECT v.difficulty, count(*) AS count
                    FROM question_versions v
                    JOIN questions q ON q.current_published_version_id=v.id
                    GROUP BY v.difficulty ORDER BY v.difficulty
                    """
                )
            ).all()
        values = dict(row)
        values["content_by_track"] = {str(key): int(count) for key, count in track_rows}
        values["content_by_difficulty"] = {str(key): int(count) for key, count in difficulty_rows}
        return CatalogAggregateSummary.model_validate(values)
