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

Availability = Literal["runnable", "published", "reference_only"]
SortOrder = Literal["relevance", "title", "difficulty", "frequency", "newest"]
CanonicalClass = Literal[
    "canonical_candidate",
    "legitimate_variant",
    "near_concept_duplicate",
    "reference_only",
    "runnable_candidate",
]

# Candidate runnable state is deliberately stronger than the old
# "approved executable solution" heuristic. A problem is runnable only when it
# is linked to the *current* published authored question version by a verified
# runtime package. Hidden/public test requirements are verified before this link
# can be promoted to verified by the runtime-link workflow.
VERIFIED_RUNTIME_LINK_SQL = """
EXISTS (
  SELECT 1
  FROM knowledge_problem_runtime_links runtime_link
  JOIN questions runtime_question ON runtime_question.id=runtime_link.question_id
  JOIN question_versions runtime_version
    ON runtime_version.id=runtime_link.question_version_id
  WHERE runtime_link.problem_id=p.id
    AND runtime_link.link_status='verified'
    AND runtime_question.current_published_version_id=runtime_link.question_version_id
    AND runtime_version.state='published'::content_state
)
""".strip()

AVAILABILITY_SQL = f"""
CASE
  WHEN p.publication_status='published'
   AND ({VERIFIED_RUNTIME_LINK_SQL}) THEN 'runnable'
  WHEN p.publication_status='published' THEN 'published'
  ELSE 'reference_only'
END
""".strip()

# Review/quarantined material is not a candidate search state. External
# reference metadata is visible only when no hosted problem body is present.
CANDIDATE_VISIBILITY_SQL = """
p.deleted_at IS NULL
AND (
  p.publication_status='published'
  OR (
    p.publication_status='metadata_only'
    AND length(trim(COALESCE(p.description, ''))) = 0
  )
)
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
    platform: str | None = None
    subtopic: str | None = None
    seniority: str | None = None
    industry: str | None = None
    canonical_classification: str | None = None
    practice_question_slug: str | None = None
    practice_runtime: str | None = None


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
    published_problems: int
    reference_only_problems: int
    statement_backed_problems: int
    python_solutions: int
    javascript_solutions: int
    sql_solutions: int
    companies: int
    topics: int
    system_design_articles: int
    source_files: int
    runtime_verified_links: int


CandidatePrincipal = Annotated[
    AuthenticatedPrincipal,
    Depends(require_permissions("catalog:read")),
]


def derive_availability(
    publication_status: str,
    *,
    has_verified_runtime_link: bool,
) -> Availability:
    """Mirror the candidate SQL availability contract for unit tests."""
    if publication_status == "published" and has_verified_runtime_link:
        return "runnable"
    if publication_status == "published":
        return "published"
    return "reference_only"


def _problem_from() -> str:
    return """
        FROM knowledge_problems p
        LEFT JOIN knowledge_problem_serving_metadata serving
          ON serving.problem_id=p.id
    """


def _problem_select() -> str:
    return f"""
        SELECT p.id, p.canonical_key, p.external_id, p.title, p.slug,
               p.summary, p.difficulty, p.source_url, p.publication_status,
               p.review_status, ({AVAILABILITY_SQL}) AS availability,
               p.acceptance_rate, p.popularity,
               serving.platform, serving.subtopic, serving.seniority,
               serving.industry, serving.canonical_classification,
               COALESCE((
                   SELECT jsonb_agg(DISTINCT solution.language ORDER BY solution.language)
                   FROM knowledge_solution_approaches approach
                   JOIN knowledge_solutions solution ON solution.approach_id=approach.id
                   WHERE approach.problem_id=p.id
                     AND solution.review_status IN (
                       'approved', 'awaiting_technical_review', 'rights_review_required'
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
               ), '[]'::jsonb) AS companies,
               (
                   SELECT runtime_question.slug
                   FROM knowledge_problem_runtime_links runtime_link
                   JOIN questions runtime_question ON runtime_question.id=runtime_link.question_id
                   JOIN question_versions runtime_version
                     ON runtime_version.id=runtime_link.question_version_id
                   WHERE runtime_link.problem_id=p.id
                     AND runtime_link.link_status='verified'
                     AND runtime_question.current_published_version_id=
                         runtime_link.question_version_id
                     AND runtime_version.state='published'::content_state
                   LIMIT 1
               ) AS practice_question_slug,
               (
                   SELECT runtime_link.runtime
                   FROM knowledge_problem_runtime_links runtime_link
                   JOIN questions runtime_question ON runtime_question.id=runtime_link.question_id
                   JOIN question_versions runtime_version
                     ON runtime_version.id=runtime_link.question_version_id
                   WHERE runtime_link.problem_id=p.id
                     AND runtime_link.link_status='verified'
                     AND runtime_question.current_published_version_id=
                         runtime_link.question_version_id
                     AND runtime_version.state='published'::content_state
                   LIMIT 1
               ) AS practice_runtime
        {_problem_from()}
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
                      WHERE {CANDIDATE_VISIBILITY_SQL}
                    )
                    SELECT
                      (SELECT count(*) FROM visible) AS problems,
                      (SELECT count(*) FROM visible WHERE availability='runnable')
                        AS runnable_problems,
                      (SELECT count(*) FROM visible WHERE availability='published')
                        AS published_problems,
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
                      (SELECT count(*) FROM knowledge_source_files) AS source_files,
                      (SELECT count(*) FROM knowledge_problem_runtime_links
                       WHERE link_status='verified') AS runtime_verified_links
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
    platform: Annotated[str | None, Query(max_length=120)] = None,
    subtopic: Annotated[str | None, Query(max_length=180)] = None,
    seniority: Annotated[str | None, Query(max_length=120)] = None,
    industry: Annotated[str | None, Query(max_length=160)] = None,
    canonical_classification: CanonicalClass | None = None,
    availability: Availability | None = None,
    sort: SortOrder = "relevance",
    page: Annotated[int, Query(ge=1, le=100_000)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 30,
) -> CatalogPage[CatalogProblemSummary]:
    del principal
    conditions = [CANDIDATE_VISIBILITY_SQL]
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
            "(EXISTS (SELECT 1 FROM knowledge_solution_approaches language_approach "
            "JOIN knowledge_solutions language_solution "
            "ON language_solution.approach_id=language_approach.id "
            "WHERE language_approach.problem_id=p.id "
            "AND language_solution.language=:language) "
            "OR (:language='python' AND EXISTS ("
            "SELECT 1 FROM knowledge_problem_runtime_links runtime_filter "
            "WHERE runtime_filter.problem_id=p.id "
            "AND runtime_filter.link_status='verified' "
            "AND runtime_filter.runtime='python')) "
            "OR (:language IN ('sql','postgresql') AND EXISTS ("
            "SELECT 1 FROM knowledge_problem_runtime_links runtime_filter "
            "WHERE runtime_filter.problem_id=p.id "
            "AND runtime_filter.link_status='verified' "
            "AND runtime_filter.runtime='postgresql')))"
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
    if platform:
        conditions.append("lower(COALESCE(serving.platform, ''))=lower(:platform)")
        parameters["platform"] = platform
    if subtopic:
        conditions.append("lower(COALESCE(serving.subtopic, ''))=lower(:subtopic)")
        parameters["subtopic"] = subtopic
    if seniority:
        conditions.append("lower(COALESCE(serving.seniority, ''))=lower(:seniority)")
        parameters["seniority"] = seniority
    if industry:
        conditions.append("lower(COALESCE(serving.industry, ''))=lower(:industry)")
        parameters["industry"] = industry
    if canonical_classification:
        conditions.append("serving.canonical_classification=:canonical_classification")
        parameters["canonical_classification"] = canonical_classification
    if availability:
        conditions.append(f"({AVAILABILITY_SQL})=:availability")
        parameters["availability"] = availability

    where = " AND ".join(conditions)
    order = {
        "relevance": (
            "ts_rank(p.search_document, websearch_to_tsquery('english', :query)) "
            "DESC, p.title ASC, p.id ASC"
            if query
            else "COALESCE(p.popularity, 0) DESC, p.title ASC, p.id ASC"
        ),
        "title": "p.title ASC, p.id ASC",
        "difficulty": (
            "CASE p.difficulty WHEN 'easy' THEN 1 WHEN 'medium' THEN 2 "
            "WHEN 'hard' THEN 3 ELSE 4 END, p.title ASC, p.id ASC"
        ),
        "frequency": (
            "COALESCE((SELECT max(frequency) "
            "FROM knowledge_company_observations "
            "WHERE problem_id=p.id), 0) DESC, p.title ASC, p.id ASC"
        ),
        "newest": "p.created_at DESC, p.id ASC",
    }[sort]
    parameters.update({"limit": page_size, "offset": (page - 1) * page_size})

    with engine.connect() as connection:
        total = int(
            connection.execute(
                text(f"SELECT count(*) {_problem_from()} WHERE {where}"),
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
                    WHERE {CANDIDATE_VISIBILITY_SQL}
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
