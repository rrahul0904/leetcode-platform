from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from .auth import require_permissions
from .database import DatabaseEngine, principal_transaction
from .published_catalog import CatalogSort, PublishedCatalogRepository
from .schemas import (
    AuthenticatedPrincipal,
    CatalogQuestion,
    Page,
    PageNumber,
    PageSize,
)

router = APIRouter(prefix="/api/v1", tags=["candidate-engagement"])


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
    company_style: Annotated[str | None, Query(max_length=100)] = None,
    completion_status: Annotated[str | None, Query(max_length=32)] = None,
    sort: CatalogSort = "relevance",
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
            company_style=company_style,
            completion_status=completion_status,
            sort=sort,
            bookmarked=True,
            connection=connection,
        )
