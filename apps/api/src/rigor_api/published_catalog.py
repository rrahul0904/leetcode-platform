from __future__ import annotations

from typing import Any, Literal

from sqlalchemy import Connection, Engine, text

from .schemas import CandidateQuestionDetail, CatalogQuestion, Page, PublicExample

CatalogSort = Literal["relevance", "title", "difficulty", "duration", "newest"]
CompletionStatus = Literal["not_started", "attempted", "passed"]


class PublishedQuestionNotFoundError(Exception):
    pass


class PublishedCatalogRepository:
    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    def list(
        self,
        *,
        page: int,
        page_size: int,
        query: str | None,
        track: str | None,
        skill: str | None,
        difficulty: str | None,
        role: str | None,
        company_style: str | None,
        completion_status: str | None,
        sort: CatalogSort,
        bookmarked: bool | None = None,
        connection: Connection | None = None,
    ) -> Page[CatalogQuestion]:
        conditions = [
            "q.current_published_version_id = v.id",
            "v.state = 'published'::content_state",
            "q.archived_at IS NULL",
        ]
        parameters: dict[str, Any] = {}
        if query:
            conditions.append(
                "(v.search_document @@ websearch_to_tsquery('english', :query) "
                "OR q.slug ILIKE '%' || :query || '%')"
            )
            parameters["query"] = query
        if track:
            conditions.append("t.slug = :track")
            parameters["track"] = track
        if difficulty:
            conditions.append("v.difficulty = :difficulty")
            parameters["difficulty"] = difficulty
        if role:
            conditions.append("v.expected_seniority = :role")
            parameters["role"] = role
        if skill:
            conditions.append(
                "EXISTS (SELECT 1 FROM question_skills qs JOIN skills s ON s.id=qs.skill_id "
                "WHERE qs.question_version_id=v.id AND s.slug=:skill)"
            )
            parameters["skill"] = skill
        if company_style:
            conditions.append(
                "EXISTS (SELECT 1 FROM question_company_tags qct "
                "JOIN company_style_tags cst ON cst.id=qct.company_style_tag_id "
                "WHERE qct.question_version_id=v.id AND cst.slug=:company_style)"
            )
            parameters["company_style"] = company_style

        current_user = "NULLIF(current_setting('rigor.user_id', true), '')::uuid"
        candidate_submission = (
            "SELECT 1 FROM submissions sub "
            "WHERE sub.question_version_id=v.id "
            f"AND sub.candidate_id={current_user}"
        )
        if completion_status == "not_started":
            conditions.append(f"NOT EXISTS ({candidate_submission})")
        elif completion_status == "attempted":
            conditions.append(f"EXISTS ({candidate_submission})")
        elif completion_status == "passed":
            conditions.append(f"EXISTS ({candidate_submission} AND sub.status='passed')")
        elif completion_status:
            conditions.append("false")

        if bookmarked is not None:
            bookmark_exists = (
                "EXISTS (SELECT 1 FROM candidate_question_bookmarks b "
                f"WHERE b.question_id=q.id AND b.user_id={current_user})"
            )
            conditions.append(bookmark_exists if bookmarked else f"NOT {bookmark_exists}")

        where = " AND ".join(conditions)
        order = {
            "relevance": (
                "ts_rank(v.search_document, websearch_to_tsquery('english', :query)) DESC, "
                "v.title ASC"
                if query
                else "v.title ASC"
            ),
            "title": "v.title ASC",
            "difficulty": (
                "CASE v.difficulty WHEN 'foundational' THEN 1 WHEN 'intermediate' THEN 2 "
                "WHEN 'advanced' THEN 3 WHEN 'staff' THEN 4 ELSE 5 END, v.title ASC"
            ),
            "duration": "v.duration_minutes ASC, v.title ASC",
            "newest": "v.created_at DESC, v.title ASC",
        }[sort]
        parameters.update({"limit": page_size, "offset": (page - 1) * page_size})

        def run(active_connection: Connection) -> Page[CatalogQuestion]:
            total = int(
                active_connection.execute(
                    text(
                        f"""
                        SELECT count(*) FROM questions q
                        JOIN question_versions v ON v.question_id=q.id
                        JOIN question_tracks t ON t.id=q.primary_track_id
                        WHERE {where}
                        """
                    ),
                    parameters,
                ).scalar_one()
            )
            rows = (
                active_connection.execute(
                    text(
                        f"""
                        SELECT q.external_id, v.title, q.slug, t.slug AS track, v.difficulty,
                               v.expected_seniority AS role_level,
                               v.duration_minutes AS estimated_duration_minutes,
                               v.version AS publication_version,
                               v.structured_content->'learning_objectives' AS learning_objectives,
                               COALESCE((
                                   SELECT jsonb_agg(s.slug ORDER BY s.slug)
                                   FROM question_skills qs JOIN skills s ON s.id=qs.skill_id
                                   WHERE qs.question_version_id=v.id
                               ), '[]'::jsonb) AS skills,
                               COALESCE((
                                   SELECT jsonb_agg(cst.slug ORDER BY cst.slug)
                                   FROM question_company_tags qct
                                   JOIN company_style_tags cst ON cst.id=qct.company_style_tag_id
                                   WHERE qct.question_version_id=v.id
                               ), '[]'::jsonb) AS company_style_tags
                        FROM questions q
                        JOIN question_versions v ON v.question_id=q.id
                        JOIN question_tracks t ON t.id=q.primary_track_id
                        WHERE {where}
                        ORDER BY {order}
                        LIMIT :limit OFFSET :offset
                        """
                    ),
                    parameters,
                )
                .mappings()
                .all()
            )
            items = [CatalogQuestion.model_validate(dict(row)) for row in rows]
            return Page[CatalogQuestion](
                items=items,
                page=page,
                page_size=page_size,
                total=total,
                has_next=page * page_size < total,
            )

        if connection is not None:
            return run(connection)
        with self.engine.connect() as standalone_connection:
            return run(standalone_connection)

    def get(self, slug: str) -> CandidateQuestionDetail:
        with self.engine.connect() as connection:
            row = (
                connection.execute(
                    text(
                        """
                        SELECT q.external_id, v.title, q.slug, t.slug AS track, v.difficulty,
                               v.expected_seniority AS role_level,
                               v.duration_minutes AS estimated_duration_minutes,
                               v.version AS publication_version,
                               v.problem_statement,
                               v.structured_content->'learning_objectives' AS learning_objectives,
                               v.structured_content->'prerequisites' AS prerequisites,
                        v.structured_content->
                            'candidate_instructions' AS candidate_instructions,
                               v.structured_content->'constraints' AS public_constraints,
                               v.structured_content#>>'{mode_specification,starter_code}'
                                   AS starter_code,
                               COALESCE((
                                   SELECT jsonb_agg(jsonb_strip_nulls(jsonb_build_object(
                                       'id', candidate_test->>'id',
                                       'name', candidate_test->>'name',
                                       'input', candidate_test->'input',
                                       'expected_output', candidate_test->'expected_output'
                                   )))
                                   FROM jsonb_array_elements(COALESCE(
                                       v.structured_content#>'{mode_specification,tests}',
                                       '[]'::jsonb
                                   )) AS candidate_test
                                   WHERE candidate_test->>'visibility' = 'public'
                               ), '[]'::jsonb) AS public_examples,
                               COALESCE((
                                   SELECT jsonb_agg(s.slug ORDER BY s.slug)
                                   FROM question_skills qs JOIN skills s ON s.id=qs.skill_id
                                   WHERE qs.question_version_id=v.id
                               ), '[]'::jsonb) AS skills,
                               COALESCE((
                                   SELECT jsonb_agg(cst.slug ORDER BY cst.slug)
                                   FROM question_company_tags qct
                                   JOIN company_style_tags cst ON cst.id=qct.company_style_tag_id
                                   WHERE qct.question_version_id=v.id
                               ), '[]'::jsonb) AS company_style_tags
                        FROM questions q
                        JOIN question_versions v ON v.id=q.current_published_version_id
                        JOIN question_tracks t ON t.id=q.primary_track_id
                        WHERE q.slug=:slug AND v.state='published'::content_state
                          AND q.archived_at IS NULL
                        """
                    ),
                    {"slug": slug},
                )
                .mappings()
                .one_or_none()
            )
        if row is None:
            raise PublishedQuestionNotFoundError
        values = dict(row)
        values["public_examples"] = [
            PublicExample.model_validate(example) for example in values["public_examples"]
        ]
        return CandidateQuestionDetail.model_validate(values)
