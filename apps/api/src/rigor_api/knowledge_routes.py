from __future__ import annotations

from typing import Annotated, Literal, cast
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text

from .auth import require_permissions
from .database import DatabaseEngine, principal_transaction
from .schemas import AuthenticatedPrincipal

router = APIRouter(prefix="/knowledge", tags=["knowledge-bank"])


class KnowledgeModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class KnowledgePage[T](KnowledgeModel):
    items: list[T]
    page: int
    page_size: int
    total: int
    has_next: bool


class ProblemSummary(KnowledgeModel):
    id: UUID
    canonical_key: str
    external_id: str | None
    title: str
    slug: str
    summary: str | None
    difficulty: str | None
    source_url: str | None
    publication_status: str
    review_status: str
    acceptance_rate: float | None
    popularity: float | None
    languages: list[str]
    topics: list[str]
    companies: list[str]


class ProblemDetail(ProblemSummary):
    description: str | None
    input_format: str | None
    output_format: str | None
    examples: list[object]
    constraints: list[object]
    hints: list[object]
    editorial_available: bool
    solution_count: int


class SolutionVariant(KnowledgeModel):
    id: UUID
    approach_id: UUID
    approach_name: str
    language: str
    runtime: str | None
    source_code: str
    explanation: str | None
    time_complexity: str | None
    space_complexity: str | None
    is_executable: bool


class CompanySummary(KnowledgeModel):
    id: UUID
    slug: str
    name: str
    problem_count: int
    easy_count: int
    medium_count: int
    hard_count: int
    average_frequency: float | None


class TopicSummary(KnowledgeModel):
    id: UUID
    slug: str
    name: str
    category: str
    problem_count: int


class SystemDesignSummary(KnowledgeModel):
    id: UUID
    slug: str
    title: str
    headings: list[str]
    image_count: int
    publication_status: str


class SystemDesignDetail(SystemDesignSummary):
    body: str
    image_paths: list[str]


class KnowledgeStats(KnowledgeModel):
    problems: int
    published_problems: int
    metadata_only_problems: int
    python_solutions: int
    javascript_solutions: int
    sql_solutions: int
    companies: int
    topics: int
    system_design_articles: int
    source_files: int


class PublicationResult(KnowledgeModel):
    id: UUID
    publication_status: str
    review_status: str
    approved_solutions: int = Field(ge=0)


CandidatePrincipal = Annotated[
    AuthenticatedPrincipal,
    Depends(require_permissions("catalog:read")),
]
PublisherPrincipal = Annotated[
    AuthenticatedPrincipal,
    Depends(require_permissions("content:publish")),
]


def _problem_select() -> str:
    return """
        SELECT p.id, p.canonical_key, p.external_id, p.title, p.slug,
               p.summary, p.difficulty, p.source_url, p.publication_status,
               p.review_status, p.acceptance_rate, p.popularity,
               COALESCE((
                   SELECT jsonb_agg(DISTINCT s.language ORDER BY s.language)
                   FROM knowledge_solution_approaches a
                   JOIN knowledge_solutions s ON s.approach_id=a.id
                   WHERE a.problem_id=p.id
                     AND s.review_status IN ('approved', 'awaiting_technical_review')
               ), '[]'::jsonb) AS languages,
               COALESCE((
                   SELECT jsonb_agg(DISTINCT t.slug ORDER BY t.slug)
                   FROM knowledge_problem_topics pt
                   JOIN knowledge_topics t ON t.id=pt.topic_id
                   WHERE pt.problem_id=p.id
               ), '[]'::jsonb) AS topics,
               COALESCE((
                   SELECT jsonb_agg(DISTINCT c.name ORDER BY c.name)
                   FROM knowledge_company_observations observation
                   JOIN knowledge_companies c ON c.id=observation.company_id
                   WHERE observation.problem_id=p.id
               ), '[]'::jsonb) AS companies
        FROM knowledge_problems p
    """


@router.get("/stats", response_model=KnowledgeStats)
def knowledge_stats(
    principal: CandidatePrincipal,
    engine: DatabaseEngine,
) -> KnowledgeStats:
    del principal
    with engine.connect() as connection:
        row = connection.execute(
            text(
                """
                SELECT
                  (SELECT count(*) FROM knowledge_problems WHERE deleted_at IS NULL) AS problems,
                  (SELECT count(*) FROM knowledge_problems
                   WHERE deleted_at IS NULL AND publication_status='published') AS published_problems,
                  (SELECT count(*) FROM knowledge_problems
                   WHERE deleted_at IS NULL AND publication_status='metadata_only')
                    AS metadata_only_problems,
                  (SELECT count(*) FROM knowledge_solutions WHERE language='python')
                    AS python_solutions,
                  (SELECT count(*) FROM knowledge_solutions WHERE language='javascript')
                    AS javascript_solutions,
                  (SELECT count(*) FROM knowledge_solutions WHERE language='sql') AS sql_solutions,
                  (SELECT count(*) FROM knowledge_companies) AS companies,
                  (SELECT count(*) FROM knowledge_topics) AS topics,
                  (SELECT count(*) FROM knowledge_system_design_articles)
                    AS system_design_articles,
                  (SELECT count(*) FROM knowledge_source_files) AS source_files
                """
            )
        ).mappings().one()
    return KnowledgeStats.model_validate(dict(row))


@router.get("/problems", response_model=KnowledgePage[ProblemSummary])
def list_problems(
    principal: CandidatePrincipal,
    engine: DatabaseEngine,
    query: Annotated[str | None, Query(max_length=160)] = None,
    difficulty: Annotated[str | None, Query(max_length=30)] = None,
    language: Annotated[str | None, Query(max_length=50)] = None,
    company: Annotated[str | None, Query(max_length=180)] = None,
    topic: Annotated[str | None, Query(max_length=180)] = None,
    sort: Literal["relevance", "title", "difficulty", "frequency", "newest"] = "relevance",
    page: Annotated[int, Query(ge=1, le=10_000)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 30,
) -> KnowledgePage[ProblemSummary]:
    del principal
    conditions = [
        "p.deleted_at IS NULL",
        "p.publication_status IN ('published', 'metadata_only')",
    ]
    parameters: dict[str, object] = {}
    if query:
        conditions.append(
            "(p.search_document @@ websearch_to_tsquery('english', :query) "
            "OR p.slug ILIKE '%' || :query || '%' "
            "OR p.external_id=:query)"
        )
        parameters["query"] = query
    if difficulty:
        conditions.append("p.difficulty=:difficulty")
        parameters["difficulty"] = difficulty.casefold()
    if language:
        conditions.append(
            "EXISTS (SELECT 1 FROM knowledge_solution_approaches la "
            "JOIN knowledge_solutions ls ON ls.approach_id=la.id "
            "WHERE la.problem_id=p.id AND ls.language=:language)"
        )
        parameters["language"] = language.casefold()
    if company:
        conditions.append(
            "EXISTS (SELECT 1 FROM knowledge_company_observations lco "
            "JOIN knowledge_companies lc ON lc.id=lco.company_id "
            "WHERE lco.problem_id=p.id AND lc.slug=:company)"
        )
        parameters["company"] = company.casefold()
    if topic:
        conditions.append(
            "EXISTS (SELECT 1 FROM knowledge_problem_topics lpt "
            "JOIN knowledge_topics lt ON lt.id=lpt.topic_id "
            "WHERE lpt.problem_id=p.id AND lt.slug=:topic)"
        )
        parameters["topic"] = topic.casefold()
    where = " AND ".join(conditions)
    order = {
        "relevance": (
            "ts_rank(p.search_document, websearch_to_tsquery('english', :query)) DESC, "
            "p.title ASC"
            if query
            else "COALESCE(p.popularity, 0) DESC, p.title ASC"
        ),
        "title": "p.title ASC",
        "difficulty": (
            "CASE p.difficulty WHEN 'easy' THEN 1 WHEN 'medium' THEN 2 "
            "WHEN 'hard' THEN 3 ELSE 4 END, p.title ASC"
        ),
        "frequency": (
            "COALESCE((SELECT max(frequency) FROM knowledge_company_observations "
            "WHERE problem_id=p.id), 0) DESC, p.title ASC"
        ),
        "newest": "p.created_at DESC, p.title ASC",
    }[sort]
    parameters.update({"limit": page_size, "offset": (page - 1) * page_size})
    with engine.connect() as connection:
        total = int(
            connection.execute(
                text(f"SELECT count(*) FROM knowledge_problems p WHERE {where}"),
                parameters,
            ).scalar_one()
        )
        rows = connection.execute(
            text(
                f"""
                {_problem_select()}
                WHERE {where}
                ORDER BY {order}
                LIMIT :limit OFFSET :offset
                """
            ),
            parameters,
        ).mappings().all()
    return KnowledgePage[ProblemSummary](
        items=[ProblemSummary.model_validate(dict(row)) for row in rows],
        page=page,
        page_size=page_size,
        total=total,
        has_next=page * page_size < total,
    )


@router.get("/problems/{slug}", response_model=ProblemDetail)
def get_problem(
    slug: str,
    principal: CandidatePrincipal,
    engine: DatabaseEngine,
) -> ProblemDetail:
    del principal
    with engine.connect() as connection:
        row = connection.execute(
            text(
                f"""
                SELECT base.*, p.description, p.input_format, p.output_format,
                       p.examples, p.constraints, p.hints,
                       (p.editorial IS NOT NULL AND length(p.editorial) > 0)
                         AS editorial_available,
                       (SELECT count(*) FROM knowledge_solution_approaches a
                        JOIN knowledge_solutions s ON s.approach_id=a.id
                        WHERE a.problem_id=p.id AND s.review_status='approved')
                         AS solution_count
                FROM ({_problem_select()} WHERE p.slug=:slug) base
                JOIN knowledge_problems p ON p.id=base.id
                WHERE p.deleted_at IS NULL
                  AND p.publication_status IN ('published', 'metadata_only')
                """
            ),
            {"slug": slug},
        ).mappings().one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Knowledge-bank problem not found")
    return ProblemDetail.model_validate(dict(row))


@router.get("/problems/{slug}/solutions", response_model=list[SolutionVariant])
def problem_solutions(
    slug: str,
    principal: CandidatePrincipal,
    engine: DatabaseEngine,
    language: Annotated[str | None, Query(max_length=50)] = None,
) -> list[SolutionVariant]:
    del principal
    parameters: dict[str, object] = {"slug": slug}
    language_condition = ""
    if language:
        parameters["language"] = language.casefold()
        language_condition = "AND s.language=:language"
    with engine.connect() as connection:
        rows = connection.execute(
            text(
                f"""
                SELECT s.id, a.id AS approach_id, a.name AS approach_name,
                       s.language, s.runtime, s.source_code, s.explanation,
                       a.time_complexity, a.space_complexity, s.is_executable
                FROM knowledge_problems p
                JOIN knowledge_solution_approaches a ON a.problem_id=p.id
                JOIN knowledge_solutions s ON s.approach_id=a.id
                WHERE p.slug=:slug
                  AND p.publication_status='published'
                  AND s.review_status='approved'
                  {language_condition}
                ORDER BY a.sequence_number, s.language, s.created_at
                """
            ),
            parameters,
        ).mappings().all()
    return [SolutionVariant.model_validate(dict(row)) for row in rows]


@router.get("/companies", response_model=list[CompanySummary])
def list_companies(
    principal: CandidatePrincipal,
    engine: DatabaseEngine,
    query: Annotated[str | None, Query(max_length=120)] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> list[CompanySummary]:
    del principal
    condition = ""
    parameters: dict[str, object] = {"limit": limit}
    if query:
        condition = "WHERE c.name ILIKE '%' || :query || '%'"
        parameters["query"] = query
    with engine.connect() as connection:
        rows = connection.execute(
            text(
                f"""
                SELECT c.id, c.slug, c.name,
                       count(DISTINCT o.problem_id) AS problem_count,
                       count(DISTINCT o.problem_id) FILTER (WHERE o.difficulty='easy')
                         AS easy_count,
                       count(DISTINCT o.problem_id) FILTER (WHERE o.difficulty='medium')
                         AS medium_count,
                       count(DISTINCT o.problem_id) FILTER (WHERE o.difficulty='hard')
                         AS hard_count,
                       avg(o.frequency) AS average_frequency
                FROM knowledge_companies c
                LEFT JOIN knowledge_company_observations o ON o.company_id=c.id
                {condition}
                GROUP BY c.id, c.slug, c.name
                ORDER BY problem_count DESC, c.name ASC
                LIMIT :limit
                """
            ),
            parameters,
        ).mappings().all()
    return [CompanySummary.model_validate(dict(row)) for row in rows]


@router.get("/companies/{slug}/problems", response_model=KnowledgePage[ProblemSummary])
def company_problems(
    slug: str,
    principal: CandidatePrincipal,
    engine: DatabaseEngine,
    page: Annotated[int, Query(ge=1, le=10_000)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 30,
) -> KnowledgePage[ProblemSummary]:
    return list_problems(
        principal,
        engine,
        company=slug,
        page=page,
        page_size=page_size,
        sort="frequency",
    )


@router.get("/topics", response_model=list[TopicSummary])
def list_topics(
    principal: CandidatePrincipal,
    engine: DatabaseEngine,
) -> list[TopicSummary]:
    del principal
    with engine.connect() as connection:
        rows = connection.execute(
            text(
                """
                SELECT t.id, t.slug, t.name, t.category,
                       count(DISTINCT pt.problem_id) AS problem_count
                FROM knowledge_topics t
                LEFT JOIN knowledge_problem_topics pt ON pt.topic_id=t.id
                GROUP BY t.id, t.slug, t.name, t.category
                ORDER BY problem_count DESC, t.name ASC
                """
            )
        ).mappings().all()
    return [TopicSummary.model_validate(dict(row)) for row in rows]


@router.get("/system-design", response_model=list[SystemDesignSummary])
def list_system_design(
    principal: CandidatePrincipal,
    engine: DatabaseEngine,
    query: Annotated[str | None, Query(max_length=160)] = None,
) -> list[SystemDesignSummary]:
    del principal
    parameters: dict[str, object] = {}
    condition = "publication_status='published'"
    if query:
        condition += " AND search_document @@ websearch_to_tsquery('english', :query)"
        parameters["query"] = query
    with engine.connect() as connection:
        rows = connection.execute(
            text(
                f"""
                SELECT id, slug, title, headings,
                       jsonb_array_length(image_paths) AS image_count,
                       publication_status
                FROM knowledge_system_design_articles
                WHERE {condition}
                ORDER BY title
                """
            ),
            parameters,
        ).mappings().all()
    return [SystemDesignSummary.model_validate(dict(row)) for row in rows]


@router.get("/system-design/{slug}", response_model=SystemDesignDetail)
def get_system_design(
    slug: str,
    principal: CandidatePrincipal,
    engine: DatabaseEngine,
) -> SystemDesignDetail:
    del principal
    with engine.connect() as connection:
        row = connection.execute(
            text(
                """
                SELECT id, slug, title, headings, body, image_paths,
                       jsonb_array_length(image_paths) AS image_count,
                       publication_status
                FROM knowledge_system_design_articles
                WHERE slug=:slug AND publication_status='published'
                """
            ),
            {"slug": slug},
        ).mappings().one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="System-design article not found")
    return SystemDesignDetail.model_validate(dict(row))


@router.post("/admin/problems/{problem_id}/publish", response_model=PublicationResult)
def publish_problem(
    problem_id: UUID,
    principal: PublisherPrincipal,
    engine: DatabaseEngine,
) -> PublicationResult:
    with principal_transaction(engine, principal) as connection:
        hostable = bool(
            connection.execute(
                text(
                    """
                    SELECT EXISTS (
                      SELECT 1
                      FROM knowledge_problem_sources ps
                      JOIN knowledge_source_files sf ON sf.id=ps.source_file_id
                      JOIN knowledge_sources source ON source.id=sf.source_id
                      WHERE ps.problem_id=:problem_id
                        AND source.disposition='hostable_licensed'
                    )
                    """
                ),
                {"problem_id": problem_id},
            ).scalar_one()
        )
        if not hostable:
            raise HTTPException(
                status_code=409,
                detail="Problem has no hostable licensed source and cannot be published.",
            )
        updated = connection.execute(
            text(
                """
                UPDATE knowledge_problems
                SET publication_status='published', review_status='approved',
                    updated_at=CURRENT_TIMESTAMP
                WHERE id=:problem_id AND deleted_at IS NULL
                RETURNING id, publication_status, review_status
                """
            ),
            {"problem_id": problem_id},
        ).mappings().one_or_none()
        if updated is None:
            raise HTTPException(status_code=404, detail="Knowledge-bank problem not found")
        solution_count = int(
            connection.execute(
                text(
                    """
                    UPDATE knowledge_solutions s
                    SET review_status='approved', updated_at=CURRENT_TIMESTAMP
                    FROM knowledge_solution_approaches a,
                         knowledge_source_files sf,
                         knowledge_sources source
                    WHERE s.approach_id=a.id
                      AND a.problem_id=:problem_id
                      AND sf.id=s.source_file_id
                      AND source.id=sf.source_id
                      AND source.disposition='hostable_licensed'
                    RETURNING s.id
                    """
                ),
                {"problem_id": problem_id},
            ).rowcount
        )
    return PublicationResult(
        id=problem_id,
        publication_status=str(updated["publication_status"]),
        review_status=str(updated["review_status"]),
        approved_solutions=solution_count,
    )


# The main application already includes the practice router. Registering this
# sub-router here avoids a second application object and preserves one versioned
# API surface for Web, iOS, and Android clients.
from .practice import router as application_router  # noqa: E402

application_router.include_router(router)
