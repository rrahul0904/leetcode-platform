from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from .auth import require_permissions
from .database import DatabaseEngine, principal_transaction
from .published_catalog import (
    CatalogSort,
    CompletionStatus,
    PublishedCatalogRepository,
)
from .schemas import (
    AuthenticatedPrincipal,
    CatalogQuestion,
    Page,
    PageNumber,
    PageSize,
)

router = APIRouter(prefix="/api/v1", tags=["candidate-engagement"])


def _candidate_catalog(
    *,
    principal: AuthenticatedPrincipal,
    engine: DatabaseEngine,
    page: int,
    page_size: int,
    query: str | None,
    track: str | None,
    skill: str | None,
    difficulty: str | None,
    role: str | None,
    question_type: str | None,
    company_style: str | None,
    completion_status: CompletionStatus | None,
    sort: CatalogSort,
    bookmarked: bool | None,
) -> Page[CatalogQuestion]:
    with principal_transaction(engine, principal) as connection:
        return PublishedCatalogRepository(engine).list(
            page=page,
            page_size=page_size,
            query=query,
            track=track,
            skill=skill,
            difficulty=difficulty,
            role=role,
            question_type=question_type,
            company_style=company_style,
            completion_status=completion_status,
            sort=sort,
            bookmarked=bookmarked,
            connection=connection,
        )


@router.get(
    "/candidate/questions",
    response_model=Page[CatalogQuestion],
)
def candidate_questions(
    principal: Annotated[
        AuthenticatedPrincipal,
        Depends(require_permissions("catalog:read")),
    ],
    engine: DatabaseEngine,
    page: PageNumber = 1,
    page_size: PageSize = 24,
    query: Annotated[str | None, Query(max_length=120)] = None,
    track: Annotated[str | None, Query(max_length=80)] = None,
    skill: Annotated[str | None, Query(max_length=100)] = None,
    difficulty: Annotated[str | None, Query(max_length=32)] = None,
    role: Annotated[str | None, Query(max_length=32)] = None,
    question_type: Annotated[str | None, Query(max_length=60)] = None,
    company_style: Annotated[str | None, Query(max_length=100)] = None,
    completion_status: CompletionStatus | None = None,
    sort: CatalogSort = "relevance",
    bookmarked: bool | None = None,
) -> Page[CatalogQuestion]:
    return _candidate_catalog(
        principal=principal,
        engine=engine,
        page=page,
        page_size=page_size,
        query=query,
        track=track,
        skill=skill,
        difficulty=difficulty,
        role=role,
        question_type=question_type,
        company_style=company_style,
        completion_status=completion_status,
        sort=sort,
        bookmarked=bookmarked,
    )


@router.get(
    "/candidate/bookmarked-questions",
    response_model=Page[CatalogQuestion],
)
def bookmarked_questions(
    principal: Annotated[
        AuthenticatedPrincipal,
        Depends(require_permissions("catalog:read")),
    ],
    engine: DatabaseEngine,
    page: PageNumber = 1,
    page_size: PageSize = 24,
    query: Annotated[str | None, Query(max_length=120)] = None,
    track: Annotated[str | None, Query(max_length=80)] = None,
    skill: Annotated[str | None, Query(max_length=100)] = None,
    difficulty: Annotated[str | None, Query(max_length=32)] = None,
    role: Annotated[str | None, Query(max_length=32)] = None,
    question_type: Annotated[str | None, Query(max_length=60)] = None,
    company_style: Annotated[str | None, Query(max_length=100)] = None,
    completion_status: CompletionStatus | None = None,
    sort: CatalogSort = "relevance",
) -> Page[CatalogQuestion]:
    return _candidate_catalog(
        principal=principal,
        engine=engine,
        page=page,
        page_size=page_size,
        query=query,
        track=track,
        skill=skill,
        difficulty=difficulty,
        role=role,
        question_type=question_type,
        company_style=company_style,
        completion_status=completion_status,
        sort=sort,
        bookmarked=True,
    )
