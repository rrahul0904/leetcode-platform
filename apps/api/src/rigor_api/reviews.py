from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import Engine, text

from .persistence import audit_event, ensure_user
from .schemas import (
    AuthenticatedPrincipal,
    ContentState,
    ReviewActionResult,
    ReviewAssignmentInput,
    ReviewAssignmentSummary,
    ReviewDecisionInput,
    ReviewKind,
    ReviewOutcome,
    ReviewQueueItem,
)


class ReviewWorkflowError(Exception):
    def __init__(self, status_code: int, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.message = message


class ReviewRepository:
    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    def queue(self, principal: AuthenticatedPrincipal) -> list[ReviewQueueItem]:
        with self.engine.begin() as connection:
            ensure_user(connection, principal)
            rows = (
                connection.execute(
                    text(
                        """
                    SELECT v.id AS question_version_id, q.external_id, q.slug, v.title,
                           v.version, v.state::text AS state,
                           author.identity_subject AS author_subject_id,
                           latest_validation.status AS validation_status
                    FROM question_versions v
                    JOIN questions q ON q.id=v.question_id
                    JOIN LATERAL (
                        SELECT p.author_id FROM provenance_records p
                        WHERE p.question_version_id=v.id ORDER BY p.created_at DESC LIMIT 1
                    ) provenance ON true
                    JOIN users author ON author.id=provenance.author_id
                    LEFT JOIN LATERAL (
                        SELECT vr.status FROM validation_runs vr
                        WHERE vr.question_version_id=v.id
                        ORDER BY vr.started_at DESC LIMIT 1
                    ) latest_validation ON true
                    WHERE v.state NOT IN ('archived'::content_state, 'deprecated'::content_state)
                    ORDER BY v.updated_at ASC, q.external_id ASC
                    """
                    )
                )
                .mappings()
                .all()
            )
            items: list[ReviewQueueItem] = []
            for row in rows:
                assignment_rows = (
                    connection.execute(
                        text(
                            """
                        SELECT a.kind::text AS kind, u.identity_subject AS reviewer_subject_id,
                               u.display_name AS reviewer_display_name, a.completed_at
                        FROM review_assignments a JOIN users u ON u.id=a.reviewer_id
                        WHERE a.question_version_id=:version_id ORDER BY a.kind::text
                        """
                        ),
                        {"version_id": row["question_version_id"]},
                    )
                    .mappings()
                    .all()
                )
                items.append(
                    ReviewQueueItem(
                        **dict(row),
                        assignments=[
                            ReviewAssignmentSummary.model_validate(dict(assignment))
                            for assignment in assignment_rows
                        ],
                    )
                )
            return items

    def assign(
        self,
        principal: AuthenticatedPrincipal,
        version_id: UUID,
        assignment: ReviewAssignmentInput,
    ) -> ReviewActionResult:
        with self.engine.begin() as connection:
            actor_id = ensure_user(connection, principal)
            version = self._lock_version(connection, version_id)
            reviewer = (
                connection.execute(
                    text(
                        """
                    SELECT u.id, u.identity_subject
                    FROM users u JOIN user_roles r ON r.user_id=u.id
                    WHERE u.identity_subject=:subject AND r.role_slug=:required_role
                    """
                    ),
                    {
                        "subject": assignment.reviewer_subject_id,
                        "required_role": f"{assignment.kind.value}-reviewer",
                    },
                )
                .mappings()
                .one_or_none()
            )
            if reviewer is None:
                raise ReviewWorkflowError(
                    422, "Reviewer identity is not provisioned with the required role"
                )
            author_subject = self._author_subject(connection, version_id)
            if reviewer["identity_subject"] == author_subject:
                raise ReviewWorkflowError(
                    409, "The author cannot review their own question version"
                )
            other_kind = "editorial" if assignment.kind == ReviewKind.technical else "technical"
            other_reviewer = connection.execute(
                text(
                    """
                    SELECT u.identity_subject FROM review_assignments a
                    JOIN users u ON u.id=a.reviewer_id
                    WHERE a.question_version_id=:version_id
                      AND a.kind=CAST(:kind AS review_kind)
                    """
                ),
                {"version_id": version_id, "kind": other_kind},
            ).scalar_one_or_none()
            if other_reviewer == reviewer["identity_subject"]:
                raise ReviewWorkflowError(
                    409, "Technical and editorial reviewers must be different"
                )
            connection.execute(
                text(
                    """
                    INSERT INTO review_assignments (question_version_id, reviewer_id, kind)
                    VALUES (:version_id, :reviewer_id, CAST(:kind AS review_kind))
                    ON CONFLICT (question_version_id, kind) DO UPDATE SET
                        reviewer_id=EXCLUDED.reviewer_id,
                        assigned_at=CURRENT_TIMESTAMP,
                        completed_at=NULL
                    """
                ),
                {
                    "version_id": version_id,
                    "reviewer_id": reviewer["id"],
                    "kind": assignment.kind.value,
                },
            )
            audit_event(
                connection,
                principal,
                actor_id,
                action="review.assigned",
                resource_type="question_version",
                resource_id=str(version_id),
                details={
                    "kind": assignment.kind.value,
                    "reviewer_subject_id": assignment.reviewer_subject_id,
                },
            )
            return ReviewActionResult(
                question_version_id=version_id,
                state=ContentState(version["state"]),
                message=f"{assignment.kind.value.title()} reviewer assigned",
            )

    def decide(
        self,
        principal: AuthenticatedPrincipal,
        version_id: UUID,
        kind: ReviewKind,
        decision: ReviewDecisionInput,
    ) -> ReviewActionResult:
        with self.engine.begin() as connection:
            reviewer_id = ensure_user(connection, principal)
            version = self._lock_version(connection, version_id)
            assignment = (
                connection.execute(
                    text(
                        """
                    SELECT id, reviewer_id FROM review_assignments
                    WHERE question_version_id=:version_id AND kind=CAST(:kind AS review_kind)
                    FOR UPDATE
                    """
                    ),
                    {"version_id": version_id, "kind": kind.value},
                )
                .mappings()
                .one_or_none()
            )
            if assignment is None or UUID(str(assignment["reviewer_id"])) != reviewer_id:
                raise ReviewWorkflowError(403, "Only the assigned reviewer can decide this review")
            if self._author_subject(connection, version_id) == principal.subject_id:
                raise ReviewWorkflowError(
                    409, "The author cannot approve their own question version"
                )
            if kind == ReviewKind.technical:
                if version["state"] != ContentState.awaiting_technical_review.value:
                    raise ReviewWorkflowError(409, "Question is not awaiting technical review")
                validation = connection.execute(
                    text(
                        """
                        SELECT status FROM validation_runs WHERE question_version_id=:version_id
                        ORDER BY started_at DESC LIMIT 1
                        """
                    ),
                    {"version_id": version_id},
                ).scalar_one_or_none()
                if validation != "passed":
                    raise ReviewWorkflowError(409, "Automated validation must pass before review")
            else:
                if version["state"] != ContentState.awaiting_editorial_review.value:
                    raise ReviewWorkflowError(409, "Question is not awaiting editorial review")
                technical_reviewer = connection.execute(
                    text(
                        """
                        SELECT reviewer_id FROM review_assignments
                        WHERE question_version_id=:version_id AND kind='technical'::review_kind
                          AND completed_at IS NOT NULL
                        """
                    ),
                    {"version_id": version_id},
                ).scalar_one_or_none()
                if technical_reviewer is None:
                    raise ReviewWorkflowError(409, "Technical approval is required first")
                if UUID(str(technical_reviewer)) == reviewer_id:
                    raise ReviewWorkflowError(
                        409, "Editorial approval requires a different reviewer"
                    )
            connection.execute(
                text(
                    """
                    INSERT INTO review_decisions (
                        review_assignment_id, reviewer_id, outcome, reason
                    ) VALUES (
                        :assignment_id, :reviewer_id, CAST(:outcome AS review_outcome), :reason
                    )
                    """
                ),
                {
                    "assignment_id": assignment["id"],
                    "reviewer_id": reviewer_id,
                    "outcome": decision.outcome.value,
                    "reason": decision.reason,
                },
            )
            connection.execute(
                text("UPDATE review_assignments SET completed_at=CURRENT_TIMESTAMP WHERE id=:id"),
                {"id": assignment["id"]},
            )
            if decision.outcome == ReviewOutcome.approved:
                next_state = (
                    ContentState.awaiting_editorial_review
                    if kind == ReviewKind.technical
                    else ContentState.approved
                )
            else:
                next_state = ContentState.draft
            connection.execute(
                text(
                    "UPDATE question_versions SET state=CAST(:state AS content_state), "
                    "updated_at=CURRENT_TIMESTAMP WHERE id=:version_id"
                ),
                {"state": next_state.value, "version_id": version_id},
            )
            audit_event(
                connection,
                principal,
                reviewer_id,
                action="review.decided",
                resource_type="question_version",
                resource_id=str(version_id),
                details={
                    "kind": kind.value,
                    "outcome": decision.outcome.value,
                    "reason": decision.reason,
                },
            )
            return ReviewActionResult(
                question_version_id=version_id,
                state=next_state,
                message=f"{kind.value.title()} review {decision.outcome.value}",
            )

    def publish(
        self,
        principal: AuthenticatedPrincipal,
        version_id: UUID,
        idempotency_key: str,
    ) -> ReviewActionResult:
        with self.engine.begin() as connection:
            publisher_id = ensure_user(connection, principal)
            version = self._lock_version(connection, version_id)
            existing = connection.execute(
                text(
                    "SELECT question_version_id FROM publication_events WHERE idempotency_key=:key"
                ),
                {"key": idempotency_key},
            ).scalar_one_or_none()
            if existing is not None:
                if UUID(str(existing)) != version_id:
                    raise ReviewWorkflowError(409, "Idempotency key was used for another version")
                return ReviewActionResult(
                    question_version_id=version_id,
                    state=ContentState.published,
                    message="Question version was already published",
                )
            if version["state"] != ContentState.approved.value:
                raise ReviewWorkflowError(409, "Only an approved version can be published")
            approvals = (
                connection.execute(
                    text(
                        """
                    SELECT a.kind::text, a.reviewer_id, d.outcome::text
                    FROM review_assignments a
                    JOIN LATERAL (
                        SELECT outcome FROM review_decisions
                        WHERE review_assignment_id=a.id ORDER BY created_at DESC LIMIT 1
                    ) d ON true
                    WHERE a.question_version_id=:version_id
                    """
                    ),
                    {"version_id": version_id},
                )
                .mappings()
                .all()
            )
            approved = {row["kind"]: row for row in approvals if row["outcome"] == "approved"}
            if set(approved) != {"technical", "editorial"}:
                raise ReviewWorkflowError(409, "Technical and editorial approvals are required")
            if approved["technical"]["reviewer_id"] == approved["editorial"]["reviewer_id"]:
                raise ReviewWorkflowError(409, "Review approvals must be independent")
            connection.execute(
                text(
                    """
                    INSERT INTO publication_events (
                        question_version_id, published_by, idempotency_key,
                        source_revision, content_hash
                    ) VALUES (
                        :version_id, :publisher_id, :key, :source_revision, :content_hash
                    )
                    """
                ),
                {
                    "version_id": version_id,
                    "publisher_id": publisher_id,
                    "key": idempotency_key,
                    "source_revision": version["source_revision"],
                    "content_hash": version["content_hash"],
                },
            )
            connection.execute(
                text("UPDATE question_versions SET state='published'::content_state WHERE id=:id"),
                {"id": version_id},
            )
            connection.execute(
                text("UPDATE questions SET current_published_version_id=:version_id WHERE id=:id"),
                {"version_id": version_id, "id": version["question_id"]},
            )
            audit_event(
                connection,
                principal,
                publisher_id,
                action="content.published",
                resource_type="question_version",
                resource_id=str(version_id),
                details={"idempotency_key": idempotency_key},
            )
            return ReviewActionResult(
                question_version_id=version_id,
                state=ContentState.published,
                message="Question version published",
            )

    def transition(
        self,
        principal: AuthenticatedPrincipal,
        version_id: UUID,
        target: ContentState,
    ) -> ReviewActionResult:
        if target not in {ContentState.deprecated, ContentState.archived}:
            raise ReviewWorkflowError(
                422, "Only deprecation and archival are administrative transitions"
            )
        with self.engine.begin() as connection:
            actor_id = ensure_user(connection, principal)
            version = self._lock_version(connection, version_id)
            if (
                target == ContentState.deprecated
                and version["state"] != ContentState.published.value
            ):
                raise ReviewWorkflowError(409, "Only published versions can be deprecated")
            if target == ContentState.archived and version["state"] == ContentState.published.value:
                raise ReviewWorkflowError(409, "Deprecate a published version before archiving it")
            connection.execute(
                text(
                    "UPDATE question_versions SET state=CAST(:state AS content_state), "
                    "updated_at=CURRENT_TIMESTAMP WHERE id=:version_id"
                ),
                {"state": target.value, "version_id": version_id},
            )
            connection.execute(
                text(
                    "UPDATE questions SET current_published_version_id=NULL, "
                    "archived_at=CASE WHEN :state='archived' "
                    "THEN CURRENT_TIMESTAMP ELSE archived_at END "
                    "WHERE id=:question_id AND current_published_version_id=:version_id"
                ),
                {
                    "state": target.value,
                    "question_id": version["question_id"],
                    "version_id": version_id,
                },
            )
            audit_event(
                connection,
                principal,
                actor_id,
                action=f"content.{target.value}",
                resource_type="question_version",
                resource_id=str(version_id),
                details={"from_state": version["state"]},
            )
            return ReviewActionResult(
                question_version_id=version_id,
                state=target,
                message=f"Question version {target.value}",
            )

    @staticmethod
    def _lock_version(connection: Any, version_id: UUID) -> dict[str, Any]:
        row = (
            connection.execute(
                text(
                    """
                SELECT id, question_id, state::text AS state, source_revision, content_hash
                FROM question_versions WHERE id=:version_id FOR UPDATE
                """
                ),
                {"version_id": version_id},
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            raise ReviewWorkflowError(404, "Question version not found")
        return dict(row)

    @staticmethod
    def _author_subject(connection: Any, version_id: UUID) -> str:
        subject = connection.execute(
            text(
                """
                SELECT u.identity_subject FROM provenance_records p
                JOIN users u ON u.id=p.author_id
                WHERE p.question_version_id=:version_id
                ORDER BY p.created_at DESC LIMIT 1
                """
            ),
            {"version_id": version_id},
        ).scalar_one_or_none()
        if subject is None:
            raise ReviewWorkflowError(409, "Question version lacks an author provenance record")
        return str(subject)
