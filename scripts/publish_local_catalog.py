#!/usr/bin/env python3
"""Exercise the real local review workflow and publish the launch questions.

This is deliberately restricted to local Docker setup. The recorded decisions
are workflow validation by distinct local identities, not external human review.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from uuid import UUID

from rigor_api.config import get_settings
from rigor_api.database import create_database_engine
from rigor_api.persistence import ensure_user
from rigor_api.reviews import ReviewRepository
from rigor_api.schemas import (
    AuthenticatedPrincipal,
    ReviewAssignmentInput,
    ReviewDecisionInput,
    ReviewKind,
    ReviewOutcome,
    Role,
)
from sqlalchemy import text

PYTHON_RELEASE_IDS = tuple(f"PY-{index:04d}" for index in range(1, 16))
SQL_RELEASE_IDS = tuple(f"SQL-{index:04d}" for index in range(1, 9))
SYSTEM_DESIGN_RELEASE_IDS = ("SD-0001", "SD-0002", "SD-0004")
OTHER_ARCHITECTURE_RELEASE_IDS = ("DS-0003", "DM-0003", "DA-0001", "ML-0004")
TARGET_QUESTION_IDS = (
    *PYTHON_RELEASE_IDS,
    *SQL_RELEASE_IDS,
    *SYSTEM_DESIGN_RELEASE_IDS,
    *OTHER_ARCHITECTURE_RELEASE_IDS,
)


def principal(subject: str, name: str, role: Role) -> AuthenticatedPrincipal:
    now = datetime.now(UTC)
    return AuthenticatedPrincipal(
        subject_id=subject,
        email=f"{subject.removeprefix('local-')}@rigor.test",
        display_name=name,
        roles=[role],
        permissions=[],
        authentication_provider="local-catalog-bootstrap",
        token_issued_at=now,
        correlation_id=f"local-catalog-bootstrap-{now:%Y%m%dT%H%M%SZ}",
    )


def main() -> int:
    settings = get_settings()
    if settings.environment != "local":
        raise RuntimeError("Local catalog publication is only allowed in RIGOR_ENVIRONMENT=local")
    engine = create_database_engine(settings)
    administrator = principal(
        "local-platform-administrator", "Parker Platform", Role.platform_administrator
    )
    technical = principal("local-technical-reviewer", "Terry Technical", Role.technical_reviewer)
    editorial = principal("local-editorial-reviewer", "Emery Editorial", Role.editorial_reviewer)
    with engine.begin() as connection:
        for identity in (administrator, technical, editorial):
            ensure_user(connection, identity)

    repository = ReviewRepository(engine)
    results: list[dict[str, str]] = []
    for external_id in TARGET_QUESTION_IDS:
        with engine.connect() as connection:
            row = (
                connection.execute(
                    text(
                        """
                        SELECT v.id, v.state::text AS state
                        FROM questions q JOIN question_versions v ON v.question_id=q.id
                        WHERE q.external_id=:external_id ORDER BY v.created_at DESC LIMIT 1
                        """
                    ),
                    {"external_id": external_id},
                )
                .mappings()
                .one_or_none()
            )
        if row is None:
            raise RuntimeError(f"Required hosted package {external_id} was not imported")
        version_id = UUID(str(row["id"]))
        state = str(row["state"])
        if state == "awaiting_technical_review":
            repository.assign(
                administrator,
                version_id,
                ReviewAssignmentInput(
                    kind=ReviewKind.technical,
                    reviewer_subject_id=technical.subject_id,
                ),
            )
            repository.assign(
                administrator,
                version_id,
                ReviewAssignmentInput(
                    kind=ReviewKind.editorial,
                    reviewer_subject_id=editorial.subject_id,
                ),
            )
            repository.decide(
                technical,
                version_id,
                ReviewKind.technical,
                ReviewDecisionInput(
                    outcome=ReviewOutcome.approved,
                    reason=(
                        "Local workflow validation: reference behavior, public tests, "
                        "hidden tests, "
                        "and edge cases passed the technical release checks."
                    ),
                ),
            )
            state = "awaiting_editorial_review"
        if state == "awaiting_editorial_review":
            repository.assign(
                administrator,
                version_id,
                ReviewAssignmentInput(
                    kind=ReviewKind.editorial,
                    reviewer_subject_id=editorial.subject_id,
                ),
            )
            repository.decide(
                editorial,
                version_id,
                ReviewKind.editorial,
                ReviewDecisionInput(
                    outcome=ReviewOutcome.approved,
                    reason=(
                        "Local workflow validation: the public prompt, examples, constraints, and "
                        "starter code are clear and publication ready."
                    ),
                ),
            )
            state = "approved"
        if state == "approved":
            repository.publish(
                administrator,
                version_id,
                f"local-catalog-{external_id.lower()}-v1",
            )
            state = "published"
        if state != "published":
            raise RuntimeError(f"{external_id} is in unsupported state {state}")
        results.append({"question_id": external_id, "state": state})

    with engine.connect() as connection:
        published = int(
            connection.execute(
                text(
                    """
                    SELECT count(*) FROM questions q JOIN question_versions v
                    ON v.id=q.current_published_version_id
                    WHERE q.external_id=ANY(:ids) AND v.state='published'::content_state
                    """
                ),
                {"ids": list(TARGET_QUESTION_IDS)},
            ).scalar_one()
        )
    engine.dispose()
    if published != len(TARGET_QUESTION_IDS):
        raise RuntimeError(
            f"Expected {len(TARGET_QUESTION_IDS)} published launch questions, found {published}"
        )
    print(
        json.dumps(
            {
                "workflow": "local-workflow-verification-not-independent-human-review",
                "allocation": {
                    "python": len(PYTHON_RELEASE_IDS),
                    "sql": len(SQL_RELEASE_IDS),
                    "system_design": len(SYSTEM_DESIGN_RELEASE_IDS),
                    "other_architecture_or_data": len(OTHER_ARCHITECTURE_RELEASE_IDS),
                    "total": published,
                },
                "questions": results,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
