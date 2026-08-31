from __future__ import annotations

import json
from typing import Any

from sqlalchemy import Engine, text

from .persistence import audit_event, ensure_user
from .schemas import AuthenticatedPrincipal, CandidateProfile, CandidateProfileInput


class ProfileNotFoundError(Exception):
    pass


class ProfileRepository:
    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    def get(self, principal: AuthenticatedPrincipal) -> CandidateProfile:
        with self.engine.begin() as connection:
            # Identity metadata may be refreshed, but external request claims must
            # never rewrite PostgreSQL-authoritative application roles.
            user_id = ensure_user(connection, principal)
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
            user_id = ensure_user(connection, principal)
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
            audit_event(
                connection,
                principal,
                user_id,
                action="profile.saved",
                resource_type="candidate_profile",
                resource_id=principal.subject_id,
                details={"completion_state": "complete"},
            )
            return self._to_profile(principal, dict(row))

    @staticmethod
    def _to_profile(principal: AuthenticatedPrincipal, values: dict[str, Any]) -> CandidateProfile:
        return CandidateProfile(
            subject_id=principal.subject_id,
            email=principal.email,
            display_name=principal.display_name,
            completion_state="complete",
            **values,
        )
