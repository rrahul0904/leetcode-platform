from __future__ import annotations

import json
from typing import Any
from uuid import UUID

from sqlalchemy import Engine, text

from .schemas import AuthenticatedPrincipal, CandidateProfile, CandidateProfileInput


class ProfileNotFoundError(Exception):
    pass


class ProfileRepository:
    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    def get(self, principal: AuthenticatedPrincipal) -> CandidateProfile:
        with self.engine.begin() as connection:
            user_id = self._ensure_user(connection, principal)
            row = (
                connection.execute(
                    text(
                        """
                        SELECT p.target_roles, p.target_companies, p.experience_level,
                               p.preferred_programming_language, p.weekly_study_hours,
                               p.interview_date, p.strong_areas, p.weak_areas,
                               p.preparation_intensity, p.completed_at, p.updated_at
                        FROM candidate_profiles p
                        WHERE p.user_id = :user_id
                        """
                    ),
                    {"user_id": user_id},
                )
                .mappings()
                .one_or_none()
            )
            if row is None:
                raise ProfileNotFoundError
            return self._to_profile(principal, dict(row))

    def put(
        self,
        principal: AuthenticatedPrincipal,
        profile: CandidateProfileInput,
    ) -> CandidateProfile:
        with self.engine.begin() as connection:
            user_id = self._ensure_user(connection, principal)
            values = profile.model_dump(mode="json")
            row = (
                connection.execute(
                    text(
                        """
                        INSERT INTO candidate_profiles (
                            user_id, target_roles, target_companies, experience_level,
                            preferred_programming_language, weekly_study_hours, interview_date,
                            strong_areas, weak_areas, preparation_intensity, completed_at
                        ) VALUES (
                            :user_id, CAST(:target_roles AS jsonb),
                            CAST(:target_companies AS jsonb),
                            :experience_level, :preferred_programming_language,
                            :weekly_study_hours, :interview_date, CAST(:strong_areas AS jsonb),
                            CAST(:weak_areas AS jsonb), :preparation_intensity, CURRENT_TIMESTAMP
                        )
                        ON CONFLICT (user_id) DO UPDATE SET
                            target_roles = EXCLUDED.target_roles,
                            target_companies = EXCLUDED.target_companies,
                            experience_level = EXCLUDED.experience_level,
                            preferred_programming_language =
                                EXCLUDED.preferred_programming_language,
                            weekly_study_hours = EXCLUDED.weekly_study_hours,
                            interview_date = EXCLUDED.interview_date,
                            strong_areas = EXCLUDED.strong_areas,
                            weak_areas = EXCLUDED.weak_areas,
                            preparation_intensity = EXCLUDED.preparation_intensity,
                            completed_at = COALESCE(
                                candidate_profiles.completed_at, CURRENT_TIMESTAMP
                            ),
                            updated_at = CURRENT_TIMESTAMP
                        RETURNING target_roles, target_companies, experience_level,
                                  preferred_programming_language, weekly_study_hours,
                                  interview_date, strong_areas, weak_areas,
                                  preparation_intensity, completed_at, updated_at
                        """
                    ),
                    {
                        "user_id": user_id,
                        "target_roles": json.dumps(values["target_roles"]),
                        "target_companies": json.dumps(values["target_companies"]),
                        "experience_level": values["experience_level"],
                        "preferred_programming_language": values["preferred_programming_language"],
                        "weekly_study_hours": values["weekly_study_hours"],
                        "interview_date": values["interview_date"],
                        "strong_areas": json.dumps(values["strong_areas"]),
                        "weak_areas": json.dumps(values["weak_areas"]),
                        "preparation_intensity": values["preparation_intensity"],
                    },
                )
                .mappings()
                .one()
            )
            connection.execute(
                text(
                    """
                    INSERT INTO audit_events (
                        actor_user_id, action, resource_type, resource_id, details, correlation_id
                    ) VALUES (
                        :user_id, 'profile.saved', 'candidate_profile', :resource_id,
                        CAST(:details AS jsonb), :correlation_id
                    )
                    """
                ),
                {
                    "user_id": user_id,
                    "resource_id": principal.subject_id,
                    "details": json.dumps({"completion_state": "complete"}),
                    "correlation_id": principal.correlation_id,
                },
            )
            return self._to_profile(principal, dict(row))

    def _ensure_user(self, connection: Any, principal: AuthenticatedPrincipal) -> UUID:
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
        connection.execute(
            text("DELETE FROM user_roles WHERE user_id = :user_id"), {"user_id": user_id}
        )
        for role in principal.roles:
            connection.execute(
                text("INSERT INTO user_roles (user_id, role_slug) VALUES (:user_id, :role)"),
                {"user_id": user_id, "role": role.value},
            )
        return UUID(str(user_id))

    @staticmethod
    def _to_profile(principal: AuthenticatedPrincipal, values: dict[str, Any]) -> CandidateProfile:
        return CandidateProfile(
            subject_id=principal.subject_id,
            email=principal.email,
            display_name=principal.display_name,
            completion_state="complete",
            **values,
        )
