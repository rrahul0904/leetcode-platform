from __future__ import annotations

from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import text

from .auth import require_permissions
from .database import DatabaseEngine
from .schemas import AuthenticatedPrincipal

router = APIRouter(prefix="/knowledge/catalog", tags=["knowledge-bank"])

Availability = Literal["runnable", "hosted", "in_review", "reference_only"]
SortOrder = Literal["relevance", "title", "difficulty", "frequency", "newest"]

AVAILABILITY_SQL = """
CASE
  WHEN p.publication_status='published'
   AND EXISTS (
     SELECT 1
     FROM knowledge_solution_approaches executable_approach
     JOIN knowledge_solutions executable_solution
       ON executable_solution.approach_id=executable_approach.id
     WHERE executable_approach.problem_id=p.id
       AND executable_solution.review_status='approved'
       AND executable_solution.is_executable
   ) THEN 'runnable'
  WHEN p.publication_status='published' THEN 'hosted'
  WHEN p.publication_status='metadata_only'
   AND length(trim(COALESCE(p.description, ''))) > 0 THEN 'in_review'
  ELSE 'reference_only'
END
""".strip()


class CatalogModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CatalogPage[T](CatalogModel):
    items: list[T]
    page: int
    page_size: int
    total: int
    has_next: bool


class CatalogProblemSummary(CatalogModel):
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
    availability: Availability
    acceptance_rate: float | None
    popularity: float | None
    languages: list[str]
    topics: list[str]
    companies: list[str]


class CatalogProblemDetail(CatalogProblemSummary):
    description: str | None
    input_format: str | None
    output_format: str | None
    examples: list[object]
    constraints: list[object]
    hints: list[object]
    editorial_available: bool
    solution_count: int


class CatalogStats(CatalogModel):
    problems: int
    runnable_problems: int
    hosted_problems: int
    in_review_problems: int
    reference_only_problems: int
    statement_backed_problems: int
    python_solutions: int
    javascript_solutions: int
    sql_solutions: int
    companies: int
    topics: int
    system_design_articles: int
    source_files: int


CandidatePrincipal = Annotated[
    AuthenticatedPrincipal,
    Depends(require_permissions("catalog:read")),
]


def derive_availability(
    publication_status: str,
    *,
    has_description: bool,
    has_executable_solution: bool,
) -> Availability:
    """Mirror the SQL availability contract for tests and non-database callers."""
    if publication_status == "published" and has_executable_solution:
        return "runnable"
    if publication_status == "published":
        return "hosted"
    if publication_status == "metadata_only" and has_description:
        return "in_review"
    return "reference_only"


def _problem_select() -> str:
    return f"""
        SELECT p.id, p.canonical_key, p.external_id, p.title, p.slug,
               p.summary, p.difficulty, p.source_url, p.publication_status,
               p.review_status, ({AVAILABILITY_SQL}) AS availability,
               p.acceptance_rate, p.popularity,
               COALESCE((
                   SELECT jsonb_agg(DISTINCT solution.language ORDER BY solution.language)
                   FROM knowledge_solution_approaches approach
                   JOIN knowledge_solutions solution ON solution.approach_id=approach.id
                   WHERE approach.problem_id=p.id
                     AND solution.review_status IN (
                       'approved', 'awaiting_technical_review'
                     )
               ), '[]'::jsonb) AS languages,
               COALESCE((
                   SELECT jsonb_agg(DISTINCT topic.slug ORDER BY topic.slug)
                   FROM knowledge_problem_topics problem_topic
                   JOIN knowledge_topics topic ON topic.id=problem_topic.topic_id
                   WHERE problem_topic.problem_id=p.id
               ), '[]'::jsonb) AS topics,
               COALESCE((
                   SELECT jsonb_agg(DISTINCT company.name ORDER BY company.name)
                   FROM knowledge_company_observations observation
                   JOIN knowledge_companies company ON company.id=observation.company_id
                   WHERE observation.problem_id=p.id
               ), '[]'::jsonb) AS companies
        FROM knowledge_problems p
    """


@router.get("/stats", response_model=CatalogStats)
def catalog_stats(
    principal: CandidatePrincipal,
    engine: DatabaseEngine,
) -> CatalogStats:
    del principal
    with engine.connect() as connection:
        row = (
            connection.execute(
                text(
                    f"""
                    WITH visible AS (
                      SELECT p.id, p.description, ({AVAILABILITY_SQL}) AS availability
                      FROM knowledge_problems p
                      WHERE p.deleted_at IS NULL
                        AND p.publication_status IN ('published', 'metadata_only')
                    )
                    SELECT
                      (SELECT count(*) FROM visible) AS problems,
                      (SELECT count(*) FROM visible WHERE availability='runnable')
                        AS runnable_problems,
                      (SELECT count(*) FROM visible WHERE availability='hosted')
                        AS hosted_problems,
                      (SELECT count(*) FROM visible WHERE availability='in_review')
                        AS in_review_problems,
                      (SELECT count(*) FROM visible WHERE availability='reference_only')
                        AS reference_only_problems,
                      (SELECT count(*) FROM visible
                       WHERE length(trim(COALESCE(description, ''))) > 0)
                        AS statement_backed_problems,
                      (SELECT count(*) FROM knowledge_solutions WHERE language='python')
                        AS python_solutions,
                      (SELECT count(*) FROM knowledge_solutions
                       WHERE language='javascript') AS javascript_solutions,
                      (SELECT count(*) FROM knowledge_solutions WHERE language='sql')
                        AS sql_solutions,
                      (SELECT count(*) FROM knowledge_companies) AS companies,
                      (SELECT count(*) FROM knowledge_topics) AS topics,
                      (SELECT count(*) FROM knowledge_system_design_articles)
                        AS system_design_articles,
                      (SELECT count(*) FROM knowledge_source_files) AS source_files
                    """
                )
            )
            .mappings()
            .one()
        )
    return CatalogStats.model_validate(dict(row))


@router.get("/problems", response_model=CatalogPage[CatalogProblemSummary])
def list_catalog_problems(
    principal: CandidatePrincipal,
    engine: DatabaseEngine,
    query: Annotated[str | None, Query(max_length=160)] = None,
    difficulty: Annotated[str | None, Query(max_length=30)] = None,
    language: Annotated[str | None, Query(max_length=50)] = None,
    company: Annotated[str | None, Query(max_length=180)] = None,
    topic: Annotated[str | None, Query(max_length=180)] = None,
    availability: Availability | None = None,
    sort: SortOrder = "relevance",
    page: Annotated[int, Query(ge=1, le=10_000)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 30,
) -> CatalogPage[CatalogProblemSummary]:
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
            "OR p.external_id=:query "
            "OR EXISTS ("
            "  SELECT 1 FROM knowledge_problem_topics search_problem_topic "
            "  JOIN knowledge_topics search_topic "
            "    ON search_topic.id=search_problem_topic.topic_id "
            "  WHERE search_problem_topic.problem_id=p.id "
            "    AND search_topic.name ILIKE '%' || :query || '%'"
            ") OR EXISTS ("
            "  SELECT 1 FROM knowledge_company_observations search_observation "
            "  JOIN knowledge_companies search_company "
            "    ON search_company.id=search_observation.company_id "
            "  WHERE search_observation.problem_id=p.id "
            "    AND search_company.name ILIKE '%' || :query || '%'"
            "))"
        )
        parameters["query"] = query
    if difficulty:
        conditions.append("p.difficulty=:difficulty")
        parameters["difficulty"] = difficulty.casefold()
    if language:
        conditions.append(
            "EXISTS (SELECT 1 FROM knowledge_solution_approaches language_approach "
            "JOIN knowledge_solutions language_solution "
            "ON language_solution.approach_id=language_approach.id "
            "WHERE language_approach.problem_id=p.id "
            "AND language_solution.language=:language)"
        )
        parameters["language"] = language.casefold()
    if company:
        conditions.append(
            "EXISTS (SELECT 1 FROM knowledge_company_observations company_observation "
            "JOIN knowledge_companies selected_company "
            "ON selected_company.id=company_observation.company_id "
            "WHERE company_observation.problem_id=p.id "
            "AND selected_company.slug=:company)"
        )
        parameters["company"] = company.casefold()
    if topic:
        conditions.append(
            "EXISTS (SELECT 1 FROM knowledge_problem_topics selected_problem_topic "
            "JOIN knowledge_topics selected_topic "
            "ON selected_topic.id=selected_problem_topic.topic_id "
            "WHERE selected_problem_topic.problem_id=p.id "
            "AND selected_topic.slug=:topic)"
        )
        parameters["topic"] = topic.casefold()
    if availability:
        conditions.append(f"({AVAILABILITY_SQL})=:availability")
        parameters["availability"] = availability

    where = " AND ".join(conditions)
    order = {
        "relevance": (
            "ts_rank(p.search_document, websearch_to_tsquery('english', :query)) "
            "DESC, p.title ASC"
            if query
            else "COALESCE(p.popularity, 0) DESC, p.title ASC"
        ),
        "title": "p.title ASC",
        "difficulty": (
            "CASE p.difficulty WHEN 'easy' THEN 1 WHEN 'medium' THEN 2 "
            "WHEN 'hard' THEN 3 ELSE 4 END, p.title ASC"
        ),
        "frequency": (
            "COALESCE((SELECT max(frequency) "
            "FROM knowledge_company_observations "
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
        rows = (
            connection.execute(
                text(
                    f"""
                    {_problem_select()}
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
    return CatalogPage[CatalogProblemSummary](
        items=[CatalogProblemSummary.model_validate(dict(row)) for row in rows],
        page=page,
        page_size=page_size,
        total=total,
        has_next=page * page_size < total,
    )


@router.get("/problems/{slug}", response_model=CatalogProblemDetail)
def get_catalog_problem(
    slug: str,
    principal: CandidatePrincipal,
    engine: DatabaseEngine,
) -> CatalogProblemDetail:
    del principal
    with engine.connect() as connection:
        row = (
            connection.execute(
                text(
                    f"""
                    SELECT base.*, p.description, p.input_format, p.output_format,
                           p.examples, p.constraints, p.hints,
                           (p.editorial IS NOT NULL AND length(p.editorial) > 0)
                             AS editorial_available,
                           (SELECT count(*)
                            FROM knowledge_solution_approaches detail_approach
                            JOIN knowledge_solutions detail_solution
                              ON detail_solution.approach_id=detail_approach.id
                            WHERE detail_approach.problem_id=p.id
                              AND detail_solution.review_status='approved')
                             AS solution_count
                    FROM ({_problem_select()} WHERE p.slug=:slug) base
                    JOIN knowledge_problems p ON p.id=base.id
                    WHERE p.deleted_at IS NULL
                      AND p.publication_status IN ('published', 'metadata_only')
                    """
                ),
                {"slug": slug},
            )
            .mappings()
            .one_or_none()
        )
    if row is None:
        raise HTTPException(status_code=404, detail="Knowledge-bank problem not found")
    return CatalogProblemDetail.model_validate(dict(row))


from .practice import router as application_router  # noqa: E402

application_router.include_router(router)
