from __future__ import annotations

import json
import os
import subprocess
import sys
from collections.abc import AsyncGenerator, Awaitable, Callable
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any, Literal
from uuid import UUID, uuid4

from fastapi import (
    Depends,
    FastAPI,
    File,
    Form,
    Header,
    HTTPException,
    Query,
    Request,
    UploadFile,
)
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from rigor_question_schema.universal import UniversalQuestion
from starlette.responses import Response

from .auth import (
    AuthenticationError,
    AuthorizationError,
    LocalOIDCProvider,
    TokenValidator,
    authenticated_principal,
    authorization_redirect,
    require_permissions,
)
from .catalog import ManifestCatalog
from .config import Settings, get_settings
from .content_factory import ContentFactory
from .database import DatabaseEngine, OperationalDatabaseEngine, create_database_engine
from .database_health import readiness_report
from .import_reports import ContentImportRepository
from .ingestion import ContentIngestionEngine, IngestionError
from .persistence import PlatformStatisticsRepository
from .practice import router as practice_router
from .profiles import ProfileNotFoundError, ProfileRepository
from .published_catalog import (
    CatalogSort,
    PublishedCatalogRepository,
    PublishedQuestionNotFoundError,
)
from .question_intelligence import QuestionIntelligenceRepository
from .reviews import ReviewRepository, ReviewWorkflowError
from .schemas import (
    AdminQuestionRecord,
    AuthenticatedPrincipal,
    CandidateProfile,
    CandidateProfileInput,
    CandidateQuestionDetail,
    CatalogAggregateSummary,
    CatalogCollectionRunResult,
    CatalogQuestion,
    CatalogSourceStatus,
    CompetencyCoverage,
    ConnectorStatus,
    ContentFactoryBatchInput,
    ContentImportReport,
    ContentImportSummary,
    ContentState,
    ContentStats,
    ContinuousCoverageStats,
    CoverageGapRecord,
    CoverageLevel,
    DuplicateCandidateRecord,
    ErrorResponse,
    ExternalReference,
    ExternalReferenceFacets,
    FieldError,
    GapRecomputeResult,
    HealthResponse,
    ImportErrorItem,
    ImportRollbackResult,
    LicenseInventoryRecord,
    LocalTokenExchange,
    ManifestQuestion,
    OIDCTokenResponse,
    Page,
    PageNumber,
    PageSize,
    PlatformStatistics,
    PracticeCatalogSummary,
    ProvenanceInventoryRecord,
    QuestionFamilyRecord,
    QuestionFreshnessRecord,
    ReadinessResponse,
    ReviewActionResult,
    ReviewAssignmentInput,
    ReviewDecisionInput,
    ReviewKind,
    ReviewQueueItem,
    SourceRegistryInput,
    SourceRegistryRecord,
    SourceReviewInput,
    SourceSyncInput,
    SourceSyncResult,
)
from .source_registry import SourceRegistryRepository
from .submissions import router as submissions_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    settings = get_settings()
    app.state.catalog = ManifestCatalog(settings.content_root / "question-bank-manifest.json")
    local_provider = LocalOIDCProvider(settings) if settings.local_oidc_enabled else None
    app.state.local_oidc_provider = local_provider
    app.state.token_validator = TokenValidator(settings, local_provider)
    app.state.database_engine = create_database_engine(settings)
    app.state.operational_database_engine = create_database_engine(
        settings, settings.operational_database_url
    )
    yield
    app.state.database_engine.dispose()
    if app.state.operational_database_engine is not app.state.database_engine:
        app.state.operational_database_engine.dispose()


app = FastAPI(
    title="Rigor API",
    version="0.1.0",
    description="Versioned API for the independent Rigor interview preparation platform.",
    lifespan=lifespan,
)
app.include_router(practice_router)
app.include_router(submissions_router)
settings: Settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Idempotency-Key", "X-Correlation-ID"],
)


@app.middleware("http")
async def correlation_id_middleware(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    correlation_id = request.headers.get("X-Correlation-ID", str(uuid4()))
    request.state.correlation_id = correlation_id
    response = await call_next(request)
    response.headers["X-Correlation-ID"] = correlation_id
    return response


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    payload = ErrorResponse(
        code="request_validation_failed",
        message="The request contains invalid fields.",
        correlation_id=getattr(request.state, "correlation_id", str(uuid4())),
        field_errors=[
            FieldError(field=".".join(str(part) for part in error["loc"]), message=error["msg"])
            for error in exc.errors()
        ],
        retryable=False,
    )
    return JSONResponse(status_code=422, content=payload.model_dump())


@app.exception_handler(AuthenticationError)
async def authentication_exception_handler(
    request: Request, exc: AuthenticationError
) -> JSONResponse:
    payload = ErrorResponse(
        code=exc.code,
        message=exc.message,
        correlation_id=getattr(request.state, "correlation_id", str(uuid4())),
        retryable=False,
    )
    return JSONResponse(
        status_code=401,
        content=payload.model_dump(),
        headers={"WWW-Authenticate": "Bearer"},
    )


@app.exception_handler(AuthorizationError)
async def authorization_exception_handler(
    request: Request, exc: AuthorizationError
) -> JSONResponse:
    payload = ErrorResponse(
        code=exc.code,
        message=exc.message,
        correlation_id=getattr(request.state, "correlation_id", str(uuid4())),
        retryable=False,
    )
    return JSONResponse(status_code=403, content=payload.model_dump())


@app.exception_handler(ReviewWorkflowError)
async def review_workflow_exception_handler(
    request: Request, exc: ReviewWorkflowError
) -> JSONResponse:
    payload = ErrorResponse(
        code="review_workflow_error",
        message=exc.message,
        correlation_id=getattr(request.state, "correlation_id", str(uuid4())),
        retryable=False,
    )
    return JSONResponse(status_code=exc.status_code, content=payload.model_dump())


@app.exception_handler(IngestionError)
async def ingestion_exception_handler(request: Request, exc: IngestionError) -> JSONResponse:
    payload = ErrorResponse(
        code="content_ingestion_error",
        message=exc.message,
        correlation_id=getattr(request.state, "correlation_id", str(uuid4())),
        retryable=False,
    )
    return JSONResponse(status_code=exc.status_code, content=payload.model_dump())


def catalog(request: Request) -> ManifestCatalog:
    value: ManifestCatalog = request.app.state.catalog
    return value


def local_oidc_provider(request: Request) -> LocalOIDCProvider:
    value: LocalOIDCProvider | None = request.app.state.local_oidc_provider
    if value is None:
        raise HTTPException(status_code=404, detail="Local OIDC is disabled")
    return value


@app.get("/livez", response_model=HealthResponse, tags=["operations"])
async def liveness() -> HealthResponse:
    return HealthResponse(status="ok")


@app.get("/readyz", response_model=ReadinessResponse, tags=["operations"])
async def readiness(request: Request, engine: DatabaseEngine) -> ReadinessResponse:
    del request
    return readiness_report(engine, settings)


@app.get("/local-oidc/.well-known/openid-configuration", tags=["local-identity"])
async def local_oidc_discovery(
    provider: Annotated[LocalOIDCProvider, Depends(local_oidc_provider)],
) -> dict[str, Any]:
    return provider.discovery()


@app.get("/local-oidc/jwks.json", tags=["local-identity"])
async def local_oidc_jwks(
    provider: Annotated[LocalOIDCProvider, Depends(local_oidc_provider)],
) -> dict[str, Any]:
    return provider.jwks()


@app.get("/local-oidc/authorize", tags=["local-identity"])
async def local_oidc_authorize(
    provider: Annotated[LocalOIDCProvider, Depends(local_oidc_provider)],
    client_id: Annotated[str, Query(max_length=120)],
    redirect_uri: Annotated[str, Query(max_length=500)],
    state: Annotated[str, Query(min_length=16, max_length=180)],
    code_challenge: Annotated[str, Query(min_length=43, max_length=128)],
    identity: Annotated[str, Query(max_length=80)],
    response_type: str = "code",
    code_challenge_method: str = "S256",
    nonce: Annotated[str | None, Query(max_length=180)] = None,
) -> RedirectResponse:
    code = provider.create_authorization_code(
        identity_key=identity,
        client_id=client_id,
        redirect_uri=redirect_uri,
        response_type=response_type,
        code_challenge=code_challenge,
        code_challenge_method=code_challenge_method,
        nonce=nonce,
    )
    return RedirectResponse(authorization_redirect(redirect_uri, code, state), status_code=302)


@app.post(
    "/local-oidc/token",
    response_model=OIDCTokenResponse,
    tags=["local-identity"],
)
async def local_oidc_token(
    exchange: LocalTokenExchange,
    provider: Annotated[LocalOIDCProvider, Depends(local_oidc_provider)],
) -> OIDCTokenResponse:
    access_token, id_token, expires_in = provider.exchange_code(
        grant_type=exchange.grant_type,
        code=exchange.code,
        client_id=exchange.client_id,
        redirect_uri=exchange.redirect_uri,
        code_verifier=exchange.code_verifier,
    )
    return OIDCTokenResponse(
        access_token=access_token,
        id_token=id_token,
        expires_in=expires_in,
    )


@app.get("/api/v1/auth/me", response_model=AuthenticatedPrincipal, tags=["identity"])
async def auth_me(
    principal: Annotated[AuthenticatedPrincipal, Depends(authenticated_principal)],
) -> AuthenticatedPrincipal:
    return principal


@app.get("/api/v1/profile", response_model=CandidateProfile, tags=["identity"])
def get_profile(
    principal: Annotated[AuthenticatedPrincipal, Depends(require_permissions("profile:read"))],
    engine: DatabaseEngine,
) -> CandidateProfile:
    try:
        return ProfileRepository(engine).get(principal)
    except ProfileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Candidate profile not found") from exc


@app.put("/api/v1/profile", response_model=CandidateProfile, tags=["identity"])
def put_profile(
    profile: CandidateProfileInput,
    principal: Annotated[AuthenticatedPrincipal, Depends(require_permissions("profile:write"))],
    engine: DatabaseEngine,
) -> CandidateProfile:
    return ProfileRepository(engine).put(principal, profile)


@app.get("/api/v1/questions", response_model=Page[CatalogQuestion], tags=["catalog"])
def published_questions(
    principal: Annotated[AuthenticatedPrincipal, Depends(require_permissions("catalog:read"))],
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
    del principal
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
    )


@app.get(
    "/api/v1/questions/{slug}",
    response_model=CandidateQuestionDetail,
    tags=["catalog"],
)
def published_question(
    slug: str,
    principal: Annotated[AuthenticatedPrincipal, Depends(require_permissions("catalog:read"))],
    engine: DatabaseEngine,
) -> CandidateQuestionDetail:
    del principal
    try:
        return PublishedCatalogRepository(engine).get(slug)
    except PublishedQuestionNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Published question not found") from exc


@app.get("/api/v1/reviews", response_model=list[ReviewQueueItem], tags=["content-review"])
def review_queue(
    principal: Annotated[AuthenticatedPrincipal, Depends(require_permissions("review:read"))],
    engine: DatabaseEngine,
) -> list[ReviewQueueItem]:
    return ReviewRepository(engine).queue(principal)


@app.put(
    "/api/v1/reviews/{question_version_id}/assignment",
    response_model=ReviewActionResult,
    tags=["content-review"],
)
def assign_reviewer(
    question_version_id: UUID,
    assignment: ReviewAssignmentInput,
    principal: Annotated[AuthenticatedPrincipal, Depends(require_permissions("review:assign"))],
    engine: DatabaseEngine,
) -> ReviewActionResult:
    return ReviewRepository(engine).assign(principal, question_version_id, assignment)


@app.post(
    "/api/v1/reviews/{question_version_id}/technical-decision",
    response_model=ReviewActionResult,
    tags=["content-review"],
)
def technical_review_decision(
    question_version_id: UUID,
    decision: ReviewDecisionInput,
    principal: Annotated[AuthenticatedPrincipal, Depends(require_permissions("review:technical"))],
    engine: DatabaseEngine,
) -> ReviewActionResult:
    return ReviewRepository(engine).decide(
        principal, question_version_id, ReviewKind.technical, decision
    )


@app.post(
    "/api/v1/reviews/{question_version_id}/editorial-decision",
    response_model=ReviewActionResult,
    tags=["content-review"],
)
def editorial_review_decision(
    question_version_id: UUID,
    decision: ReviewDecisionInput,
    principal: Annotated[AuthenticatedPrincipal, Depends(require_permissions("review:editorial"))],
    engine: DatabaseEngine,
) -> ReviewActionResult:
    return ReviewRepository(engine).decide(
        principal, question_version_id, ReviewKind.editorial, decision
    )


@app.post(
    "/api/v1/reviews/{question_version_id}/publish",
    response_model=ReviewActionResult,
    tags=["content-review"],
)
def publish_question_version(
    question_version_id: UUID,
    principal: Annotated[AuthenticatedPrincipal, Depends(require_permissions("content:publish"))],
    engine: DatabaseEngine,
    idempotency_key: Annotated[str, Header(min_length=8, max_length=120)],
) -> ReviewActionResult:
    return ReviewRepository(engine).publish(principal, question_version_id, idempotency_key)


@app.post(
    "/api/v1/reviews/{question_version_id}/transition/{target}",
    response_model=ReviewActionResult,
    tags=["content-review"],
)
def transition_question_version(
    question_version_id: UUID,
    target: ContentState,
    principal: Annotated[
        AuthenticatedPrincipal, Depends(require_permissions("content:transition"))
    ],
    engine: DatabaseEngine,
) -> ReviewActionResult:
    return ReviewRepository(engine).transition(principal, question_version_id, target)


async def _run_uploaded_import(
    *,
    file: UploadFile,
    principal: AuthenticatedPrincipal,
    engine: Any,
    dry_run: bool,
    visibility: Literal["public", "private"],
) -> ContentImportReport:
    content = await file.read(25 * 1024 * 1024 + 1)
    result = ContentIngestionEngine(engine).import_upload(
        principal,
        filename=file.filename or "upload",
        content=content,
        dry_run=dry_run,
        visibility=visibility,
    )
    return ContentImportRepository(engine).get(principal, UUID(result.import_id))


@app.post(
    "/api/v1/admin/content/imports",
    response_model=ContentImportReport,
    tags=["content-ingestion"],
)
async def create_content_import(
    file: Annotated[UploadFile, File()],
    principal: Annotated[AuthenticatedPrincipal, Depends(require_permissions("content:import"))],
    engine: DatabaseEngine,
    dry_run: Annotated[bool, Form()] = False,
    visibility: Annotated[Literal["public", "private"], Form()] = "public",
) -> ContentImportReport:
    return await _run_uploaded_import(
        file=file,
        principal=principal,
        engine=engine,
        dry_run=dry_run,
        visibility=visibility,
    )


@app.post(
    "/api/v1/admin/content/imports/validate",
    response_model=ContentImportReport,
    tags=["content-ingestion"],
)
async def validate_content_import(
    file: Annotated[UploadFile, File()],
    principal: Annotated[AuthenticatedPrincipal, Depends(require_permissions("content:import"))],
    engine: DatabaseEngine,
    visibility: Annotated[Literal["public", "private"], Form()] = "public",
) -> ContentImportReport:
    return await _run_uploaded_import(
        file=file,
        principal=principal,
        engine=engine,
        dry_run=True,
        visibility=visibility,
    )


@app.get(
    "/api/v1/admin/content/imports",
    response_model=list[ContentImportSummary],
    tags=["content-ingestion"],
)
def list_content_imports(
    principal: Annotated[AuthenticatedPrincipal, Depends(require_permissions("content:import"))],
    engine: DatabaseEngine,
) -> list[ContentImportSummary]:
    return ContentImportRepository(engine).list(principal)


@app.get(
    "/api/v1/admin/content/imports/{import_id}",
    response_model=ContentImportReport,
    tags=["content-ingestion"],
)
def get_content_import(
    import_id: UUID,
    principal: Annotated[AuthenticatedPrincipal, Depends(require_permissions("content:import"))],
    engine: DatabaseEngine,
) -> ContentImportReport:
    return ContentImportRepository(engine).get(principal, import_id)


@app.get(
    "/api/v1/admin/content/imports/{import_id}/errors",
    response_model=list[ImportErrorItem],
    tags=["content-ingestion"],
)
def get_content_import_errors(
    import_id: UUID,
    principal: Annotated[AuthenticatedPrincipal, Depends(require_permissions("content:import"))],
    engine: DatabaseEngine,
) -> list[ImportErrorItem]:
    return ContentImportRepository(engine).errors(principal, import_id)


@app.get(
    "/api/v1/admin/content/imports/{import_id}/report",
    response_class=Response,
    tags=["content-ingestion"],
)
def download_content_import_report(
    import_id: UUID,
    principal: Annotated[AuthenticatedPrincipal, Depends(require_permissions("content:import"))],
    engine: DatabaseEngine,
) -> Response:
    payload = ContentImportRepository(engine).payload(principal, import_id)
    return Response(
        payload,
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="content-import-{import_id}.json"'},
    )


@app.post(
    "/api/v1/admin/content/imports/{import_id}/retry",
    response_model=ContentImportReport,
    tags=["content-ingestion"],
)
async def retry_content_import(
    import_id: UUID,
    file: Annotated[UploadFile, File()],
    principal: Annotated[AuthenticatedPrincipal, Depends(require_permissions("content:import"))],
    engine: DatabaseEngine,
    dry_run: Annotated[bool, Form()] = False,
    visibility: Annotated[Literal["public", "private"], Form()] = "public",
) -> ContentImportReport:
    ContentImportRepository(engine).get(principal, import_id)
    return await _run_uploaded_import(
        file=file,
        principal=principal,
        engine=engine,
        dry_run=dry_run,
        visibility=visibility,
    )


@app.post(
    "/api/v1/admin/content/imports/{import_id}/rollback",
    response_model=ImportRollbackResult,
    tags=["content-ingestion"],
)
def rollback_content_import(
    import_id: UUID,
    principal: Annotated[AuthenticatedPrincipal, Depends(require_permissions("content:import"))],
    engine: DatabaseEngine,
) -> ImportRollbackResult:
    return ContentImportRepository(engine).rollback(principal, import_id)


@app.post(
    "/api/v1/admin/questions",
    response_model=ContentImportReport,
    tags=["content-authoring"],
)
def author_question(
    question: UniversalQuestion,
    principal: Annotated[AuthenticatedPrincipal, Depends(require_permissions("content:authoring"))],
    engine: DatabaseEngine,
) -> ContentImportReport:
    payload = json.dumps(question.model_dump(mode="json")).encode("utf-8")
    result = ContentIngestionEngine(engine).import_upload(
        principal,
        filename=f"authoring-{question.id}.json",
        content=payload,
        dry_run=False,
    )
    return ContentImportRepository(engine).get(principal, UUID(result.import_id))


@app.put(
    "/api/v1/admin/questions/{question_id}",
    response_model=ContentImportReport,
    tags=["content-authoring"],
)
def edit_question(
    question_id: str,
    question: UniversalQuestion,
    principal: Annotated[AuthenticatedPrincipal, Depends(require_permissions("content:authoring"))],
    engine: DatabaseEngine,
) -> ContentImportReport:
    if question.id != question_id:
        raise IngestionError(422, "Path question ID must match the authored package ID")
    return author_question(question, principal, engine)


@app.post(
    "/api/v1/admin/content/factory/batches",
    response_model=ContentImportReport,
    tags=["content-factory"],
)
def run_content_factory_batch(
    batch: ContentFactoryBatchInput,
    principal: Annotated[AuthenticatedPrincipal, Depends(require_permissions("content:authoring"))],
    engine: DatabaseEngine,
) -> ContentImportReport:
    return ContentFactory(engine).run(principal, batch)


@app.get(
    "/api/v1/admin/questions",
    response_model=list[AdminQuestionRecord],
    tags=["question-intelligence"],
)
def list_admin_questions(
    _: Annotated[AuthenticatedPrincipal, Depends(require_permissions("content:read-private"))],
    engine: DatabaseEngine,
) -> list[AdminQuestionRecord]:
    return QuestionIntelligenceRepository(engine).questions()


@app.get(
    "/api/v1/admin/questions/duplicates",
    response_model=list[DuplicateCandidateRecord],
    tags=["question-intelligence"],
)
def list_duplicate_candidates(
    _: Annotated[AuthenticatedPrincipal, Depends(require_permissions("content:read-private"))],
    engine: DatabaseEngine,
) -> list[DuplicateCandidateRecord]:
    return QuestionIntelligenceRepository(engine).duplicates()


@app.get(
    "/api/v1/admin/questions/families",
    response_model=list[QuestionFamilyRecord],
    tags=["question-intelligence"],
)
def list_question_families(
    _: Annotated[AuthenticatedPrincipal, Depends(require_permissions("content:read-private"))],
    engine: DatabaseEngine,
) -> list[QuestionFamilyRecord]:
    return QuestionIntelligenceRepository(engine).families()


@app.get(
    "/api/v1/admin/questions/gaps",
    response_model=list[CoverageGapRecord],
    tags=["question-intelligence"],
)
def list_coverage_gaps(
    _: Annotated[AuthenticatedPrincipal, Depends(require_permissions("coverage:read"))],
    engine: DatabaseEngine,
) -> list[CoverageGapRecord]:
    return QuestionIntelligenceRepository(engine).gaps()


@app.post(
    "/api/v1/admin/questions/gaps/recompute",
    response_model=GapRecomputeResult,
    tags=["question-intelligence"],
)
def recompute_coverage_gaps(
    principal: Annotated[AuthenticatedPrincipal, Depends(require_permissions("source:manage"))],
    engine: DatabaseEngine,
) -> GapRecomputeResult:
    return QuestionIntelligenceRepository(engine).recompute_gaps(principal)


@app.get(
    "/api/v1/admin/questions/freshness",
    response_model=list[QuestionFreshnessRecord],
    tags=["question-intelligence"],
)
def list_question_freshness(
    _: Annotated[AuthenticatedPrincipal, Depends(require_permissions("content:read-private"))],
    engine: DatabaseEngine,
) -> list[QuestionFreshnessRecord]:
    return QuestionIntelligenceRepository(engine).freshness()


@app.get(
    "/api/v1/admin/questions/licenses",
    response_model=list[LicenseInventoryRecord],
    tags=["question-intelligence"],
)
def list_question_licenses(
    _: Annotated[AuthenticatedPrincipal, Depends(require_permissions("content:read-private"))],
    engine: DatabaseEngine,
) -> list[LicenseInventoryRecord]:
    return QuestionIntelligenceRepository(engine).licenses()


@app.get(
    "/api/v1/admin/questions/provenance",
    response_model=list[ProvenanceInventoryRecord],
    tags=["question-intelligence"],
)
def list_question_provenance(
    _: Annotated[AuthenticatedPrincipal, Depends(require_permissions("content:read-private"))],
    engine: DatabaseEngine,
) -> list[ProvenanceInventoryRecord]:
    return QuestionIntelligenceRepository(engine).provenance()


@app.post(
    "/api/v1/admin/sources",
    response_model=SourceRegistryRecord,
    tags=["source-registry"],
)
def register_source(
    source: SourceRegistryInput,
    principal: Annotated[AuthenticatedPrincipal, Depends(require_permissions("source:manage"))],
    engine: DatabaseEngine,
) -> SourceRegistryRecord:
    return SourceRegistryRepository(engine).register(principal, source)


@app.get(
    "/api/v1/admin/sources",
    response_model=list[SourceRegistryRecord],
    tags=["source-registry"],
)
def list_sources(
    principal: Annotated[AuthenticatedPrincipal, Depends(require_permissions("source:read"))],
    engine: DatabaseEngine,
    connector_status: ConnectorStatus | None = None,
    coverage_level: CoverageLevel | None = None,
) -> list[SourceRegistryRecord]:
    return SourceRegistryRepository(engine).list(
        principal,
        connector_status=connector_status,
        coverage_level=coverage_level,
    )


@app.get(
    "/api/v1/admin/sources/{source_id}",
    response_model=SourceRegistryRecord,
    tags=["source-registry"],
)
def get_source(
    source_id: UUID,
    principal: Annotated[AuthenticatedPrincipal, Depends(require_permissions("source:read"))],
    engine: DatabaseEngine,
) -> SourceRegistryRecord:
    return SourceRegistryRepository(engine).get(principal, source_id)


@app.put(
    "/api/v1/admin/sources/{source_id}/review",
    response_model=SourceRegistryRecord,
    tags=["source-registry"],
)
def review_source(
    source_id: UUID,
    review: SourceReviewInput,
    principal: Annotated[AuthenticatedPrincipal, Depends(require_permissions("source:manage"))],
    engine: DatabaseEngine,
) -> SourceRegistryRecord:
    return SourceRegistryRepository(engine).review(principal, source_id, review)


@app.post(
    "/api/v1/admin/sources/{source_id}/sync",
    response_model=SourceSyncResult,
    tags=["source-registry"],
)
def synchronize_source(
    source_id: UUID,
    sync: SourceSyncInput,
    principal: Annotated[AuthenticatedPrincipal, Depends(require_permissions("source:manage"))],
    engine: DatabaseEngine,
) -> SourceSyncResult:
    return SourceRegistryRepository(engine).sync(principal, source_id, sync)


@app.get(
    "/api/v1/external-references",
    response_model=Page[ExternalReference],
    tags=["content-intelligence"],
)
def external_references(
    principal: Annotated[AuthenticatedPrincipal, Depends(require_permissions("catalog:read"))],
    engine: DatabaseEngine,
    page: PageNumber = 1,
    page_size: PageSize = 24,
    query: Annotated[str | None, Query(max_length=120)] = None,
    source_id: UUID | None = None,
    difficulty: Annotated[str | None, Query(max_length=40)] = None,
    competency: Annotated[str | None, Query(max_length=100)] = None,
) -> Page[ExternalReference]:
    del principal
    items, total = SourceRegistryRepository(engine).external_references(
        query=query,
        source_id=source_id,
        difficulty=difficulty,
        competency=competency,
        page=page,
        page_size=page_size,
    )
    return Page[ExternalReference](
        items=items,
        page=page,
        page_size=page_size,
        total=total,
        has_next=page * page_size < total,
    )


@app.get(
    "/api/v1/external-reference-facets",
    response_model=ExternalReferenceFacets,
    tags=["content-intelligence"],
)
def external_reference_facets(
    principal: Annotated[AuthenticatedPrincipal, Depends(require_permissions("catalog:read"))],
    engine: DatabaseEngine,
) -> ExternalReferenceFacets:
    del principal
    return SourceRegistryRepository(engine).external_reference_facets()


@app.get(
    "/api/v1/practice/summary",
    response_model=PracticeCatalogSummary,
    tags=["catalog"],
)
def practice_summary(
    principal: Annotated[AuthenticatedPrincipal, Depends(require_permissions("catalog:read"))],
    engine: DatabaseEngine,
) -> PracticeCatalogSummary:
    del principal
    return SourceRegistryRepository(engine).practice_summary()


@app.get(
    "/api/v1/admin/catalog/status",
    response_model=list[CatalogSourceStatus],
    tags=["source-registry"],
)
def catalog_status(
    principal: Annotated[AuthenticatedPrincipal, Depends(require_permissions("source:read"))],
    engine: DatabaseEngine,
) -> list[CatalogSourceStatus]:
    del principal
    return SourceRegistryRepository(engine).catalog_status()


@app.get(
    "/api/v1/admin/catalog/summary",
    response_model=CatalogAggregateSummary,
    tags=["source-registry"],
)
def aggregate_catalog_summary(
    principal: Annotated[AuthenticatedPrincipal, Depends(require_permissions("source:read"))],
    engine: OperationalDatabaseEngine,
) -> CatalogAggregateSummary:
    del principal
    return PlatformStatisticsRepository(engine).catalog_summary()


@app.get(
    "/api/v1/platform/statistics",
    response_model=PlatformStatistics,
    tags=["operations"],
)
def platform_statistics(
    principal: Annotated[AuthenticatedPrincipal, Depends(require_permissions("source:read"))],
    engine: OperationalDatabaseEngine,
) -> PlatformStatistics:
    del principal
    return PlatformStatisticsRepository(engine).statistics()


@app.post(
    "/api/v1/admin/catalog/collect",
    response_model=CatalogCollectionRunResult,
    tags=["source-registry"],
)
def run_approved_collectors(
    principal: Annotated[AuthenticatedPrincipal, Depends(require_permissions("source:manage"))],
    engine: DatabaseEngine,
) -> CatalogCollectionRunResult:
    del principal
    if settings.environment not in {"local", "development", "test"}:
        raise HTTPException(status_code=403, detail="Interactive collection is local-only")
    collector = Path("/app/scripts/collect_external_references.py")
    if not collector.exists():
        collector = Path(__file__).resolve().parents[4] / "scripts/collect_external_references.py"
    command = [sys.executable, str(collector)]
    ca_file = Path("/run/secrets/build_ca")
    if ca_file.exists():
        command.extend(["--ca-file", str(ca_file)])
    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
        env={**os.environ, "RIGOR_DATABASE_URL": settings.database_url},
    )
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "Collector failed").strip()[-2000:]
        raise HTTPException(status_code=502, detail=detail)
    summary = SourceRegistryRepository(engine).practice_summary()
    return CatalogCollectionRunResult(
        external_references=summary.external_references,
        completed_at=datetime.now(UTC),
    )


@app.get(
    "/api/v1/admin/coverage",
    response_model=ContinuousCoverageStats,
    tags=["content-intelligence"],
)
def continuous_coverage(
    principal: Annotated[AuthenticatedPrincipal, Depends(require_permissions("coverage:read"))],
    engine: DatabaseEngine,
    repository: Annotated[ManifestCatalog, Depends(catalog)],
) -> ContinuousCoverageStats:
    del principal
    return SourceRegistryRepository(engine).coverage(repository.stats().planned_questions)


@app.get(
    "/api/v1/admin/coverage/competencies",
    response_model=list[CompetencyCoverage],
    tags=["content-intelligence"],
)
def competency_coverage(
    principal: Annotated[AuthenticatedPrincipal, Depends(require_permissions("coverage:read"))],
    engine: DatabaseEngine,
) -> list[CompetencyCoverage]:
    del principal
    return SourceRegistryRepository(engine).competency_coverage()


@app.get("/api/v1/content/stats", response_model=ContentStats, tags=["content-foundation"])
async def content_stats(repository: Annotated[ManifestCatalog, Depends(catalog)]) -> ContentStats:
    return repository.stats()


@app.get(
    "/api/v1/manifest/questions",
    response_model=Page[ManifestQuestion],
    tags=["content-foundation"],
    summary="Inspect planned manifest metadata; not a published candidate catalog",
)
async def manifest_questions(
    repository: Annotated[ManifestCatalog, Depends(catalog)],
    page: PageNumber = 1,
    page_size: PageSize = 24,
    query: Annotated[str | None, Query(max_length=120)] = None,
    track: Annotated[str | None, Query(max_length=80)] = None,
    difficulty: Annotated[str | None, Query(max_length=32)] = None,
) -> Page[ManifestQuestion]:
    return repository.list_planned(
        page=page,
        page_size=page_size,
        query=query,
        track=track,
        difficulty=difficulty,
    )


@app.get(
    "/api/v1/manifest/questions/{slug}",
    response_model=ManifestQuestion,
    tags=["content-foundation"],
    summary="Inspect one planned manifest brief; no private package fields are exposed",
)
async def manifest_question(
    slug: str,
    repository: Annotated[ManifestCatalog, Depends(catalog)],
) -> ManifestQuestion:
    question = repository.get_planned_by_slug(slug)
    if question is None:
        raise HTTPException(status_code=404, detail="Planned question not found")
    return question
