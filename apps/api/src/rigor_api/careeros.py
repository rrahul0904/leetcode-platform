from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from collections.abc import Mapping
from datetime import datetime
from typing import Annotated, Any, Literal, cast
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import Connection, text

from .auth import authenticated_principal
from .database import DatabaseEngine, principal_transaction
from .schemas import AuthenticatedPrincipal, Role

router = APIRouter(prefix="/api/v1/career", tags=["career-os"])

CareerJobStatus = Literal[
    "saved",
    "tailored",
    "applied",
    "screen",
    "interview",
    "offer",
    "rejected",
    "withdrawn",
]
CAREER_JOB_STATUSES = {
    "saved",
    "tailored",
    "applied",
    "screen",
    "interview",
    "offer",
    "rejected",
    "withdrawn",
}
SCORING_VERSION = "deterministic-v1"
_CURRENT_USER_SQL = "NULLIF(current_setting('rigor.user_id', true), '')::uuid"


class CareerJobAnalysisInput(BaseModel):
    job_title: str | None = Field(default=None, max_length=160)
    company: str | None = Field(default=None, max_length=160)
    source_url: str | None = Field(default=None, max_length=2000)
    resume_text: str = Field(min_length=40, max_length=100_000)
    job_description: str = Field(min_length=40, max_length=100_000)


class CareerInterviewQuestion(BaseModel):
    category: Literal["experience", "technical", "gap", "behavioral", "system-design"]
    focus: str
    question: str
    coaching_note: str


class CareerJobAnalysis(BaseModel):
    job_title: str | None
    company: str | None
    source_url: str | None
    fit_score: int = Field(ge=0, le=100)
    skill_coverage: int = Field(ge=0, le=100)
    language_overlap: int = Field(ge=0, le=100)
    matched_skills: list[str]
    missing_skills: list[str]
    resume_skills: list[str]
    priority_keywords: list[str]
    strengths: list[str]
    risks: list[str]
    interview_questions: list[CareerInterviewQuestion]
    scoring_explanation: str


class CareerSavedAnalysis(CareerJobAnalysis):
    job_id: UUID
    document_id: UUID
    analysis_id: UUID
    status: CareerJobStatus
    scoring_version: str
    created_at: datetime


class CareerJobSummary(BaseModel):
    id: UUID
    job_title: str | None
    company: str | None
    source_url: str | None
    status: CareerJobStatus
    latest_fit_score: int | None
    matched_skills: list[str]
    missing_skills: list[str]
    analysis_count: int
    last_analyzed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class CareerJobStatusInput(BaseModel):
    status: CareerJobStatus


# Display name -> aliases. This is intentionally explicit and deterministic so users can
# understand why a skill was classified as present or missing. Model-backed enrichment can
# add synonyms later without changing the public response contract.
SKILL_ALIASES: dict[str, tuple[str, ...]] = {
    "Python": ("python",),
    "Java": ("java",),
    "JavaScript": ("javascript", "js"),
    "TypeScript": ("typescript", "ts"),
    "React": ("react", "reactjs", "react.js"),
    "Next.js": ("next.js", "nextjs"),
    "Node.js": ("node.js", "nodejs"),
    "FastAPI": ("fastapi",),
    "Django": ("django",),
    "Flask": ("flask",),
    "SQL": ("sql",),
    "PostgreSQL": ("postgresql", "postgres"),
    "MySQL": ("mysql",),
    "Snowflake": ("snowflake",),
    "Databricks": ("databricks",),
    "Spark": ("apache spark", "pyspark", "spark"),
    "dbt": ("dbt",),
    "AWS": ("aws", "amazon web services"),
    "Azure": ("azure",),
    "GCP": ("gcp", "google cloud", "google cloud platform"),
    "Docker": ("docker", "containerization", "containers"),
    "Kubernetes": ("kubernetes", "k8s"),
    "Terraform": ("terraform", "infrastructure as code", "iac"),
    "Kafka": ("kafka", "apache kafka"),
    "Redis": ("redis",),
    "GraphQL": ("graphql",),
    "REST APIs": ("rest api", "restful", "rest apis"),
    "CI/CD": ("ci/cd", "continuous integration", "continuous delivery", "continuous deployment"),
    "Git": ("git", "github", "gitlab"),
    "Linux": ("linux",),
    "Machine Learning": ("machine learning", "ml"),
    "LLMs": ("large language model", "large language models", "llm", "llms"),
    "RAG": ("retrieval augmented generation", "retrieval-augmented generation", "rag"),
    "Data Engineering": ("data engineering", "data pipelines", "etl", "elt"),
    "Data Modeling": ("data modeling", "data modelling", "dimensional modeling"),
    "System Design": ("system design", "distributed systems", "scalable systems"),
    "Microservices": ("microservices", "microservice architecture"),
    "Observability": ("observability", "opentelemetry", "distributed tracing"),
    "Security": ("application security", "cybersecurity", "security"),
    "Agile": ("agile", "scrum"),
}

STOP_WORDS = {
    "about",
    "after",
    "again",
    "also",
    "and",
    "are",
    "been",
    "being",
    "build",
    "but",
    "can",
    "company",
    "experience",
    "for",
    "from",
    "have",
    "into",
    "job",
    "more",
    "our",
    "role",
    "that",
    "the",
    "their",
    "this",
    "through",
    "using",
    "will",
    "with",
    "work",
    "you",
    "your",
}


def _normalize(value: str) -> str:
    return re.sub(r"\s+", " ", value.casefold()).strip()


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _contains_alias(text: str, alias: str) -> bool:
    # Word-like boundaries prevent short aliases such as JS/TS/ML from matching inside
    # unrelated words while still supporting punctuation-heavy skills such as CI/CD.
    pattern = rf"(?<![a-z0-9]){re.escape(alias.casefold())}(?![a-z0-9])"
    return re.search(pattern, text) is not None


def _extract_skills(value: str) -> list[str]:
    normalized = _normalize(value)
    return [
        display_name
        for display_name, aliases in SKILL_ALIASES.items()
        if any(_contains_alias(normalized, alias) for alias in aliases)
    ]


def _tokens(value: str) -> list[str]:
    return [
        token
        for token in re.findall(r"[a-z][a-z0-9+#.-]{2,}", value.casefold())
        if token not in STOP_WORDS and not token.isdigit()
    ]


def _priority_keywords(job_description: str, *, limit: int = 12) -> list[str]:
    counts = Counter(_tokens(job_description))
    return [token for token, _ in counts.most_common(limit)]


def _language_overlap(resume_text: str, job_description: str) -> int:
    resume = set(_tokens(resume_text))
    job_counts = Counter(_tokens(job_description))
    if not job_counts:
        return 0
    important = {token for token, _ in job_counts.most_common(60)}
    if not important:
        return 0
    return round(100 * len(resume & important) / len(important))


def _build_questions(
    payload: CareerJobAnalysisInput,
    matched: list[str],
    missing: list[str],
) -> list[CareerInterviewQuestion]:
    questions: list[CareerInterviewQuestion] = []

    for skill in matched[:3]:
        questions.append(
            CareerInterviewQuestion(
                category="experience",
                focus=skill,
                question=(
                    f"Walk me through a project where you used {skill}. "
                    "What did you personally own, what trade-offs did you make, and what changed?"
                ),
                coaching_note=(
                    "Use a concrete example with scope, decisions, measurable impact, "
                    "and lessons learned."
                ),
            )
        )

    for skill in missing[:3]:
        questions.append(
            CareerInterviewQuestion(
                category="gap",
                focus=skill,
                question=(
                    f"This role emphasizes {skill}, but it is not explicit in your resume. "
                    "What adjacent experience would let you become productive with it quickly?"
                ),
                coaching_note=(
                    "Do not bluff. Bridge from a neighboring skill and describe a credible "
                    "learning plan."
                ),
            )
        )

    title = payload.job_title or "this role"
    questions.append(
        CareerInterviewQuestion(
            category="system-design",
            focus="architecture",
            question=(
                f"For {title}, design a production system that must scale while remaining "
                "reliable. How would you decompose it, store data, observe failures, and "
                "evolve it safely?"
            ),
            coaching_note=(
                "Clarify requirements first, state assumptions, then discuss components "
                "and trade-offs."
            ),
        )
    )
    questions.append(
        CareerInterviewQuestion(
            category="behavioral",
            focus="ownership",
            question=(
                "Tell me about a high-impact problem you owned when requirements were ambiguous. "
                "How did you decide what to do, align people, and measure whether it worked?"
            ),
            coaching_note=(
                "Structure the answer as situation, task, actions, result, and reflection."
            ),
        )
    )
    return questions[:8]


def analyze_job(payload: CareerJobAnalysisInput) -> CareerJobAnalysis:
    job_skills = _extract_skills(payload.job_description)
    resume_skills = _extract_skills(payload.resume_text)
    resume_skill_set = set(resume_skills)
    matched = [skill for skill in job_skills if skill in resume_skill_set]
    missing = [skill for skill in job_skills if skill not in resume_skill_set]

    language_overlap = _language_overlap(payload.resume_text, payload.job_description)
    skill_coverage = (
        round(100 * len(matched) / len(job_skills)) if job_skills else language_overlap
    )
    fit_score = round(0.72 * skill_coverage + 0.28 * language_overlap)
    fit_score = max(0, min(100, fit_score))

    strengths = [
        (
            f"Your resume contains direct evidence for {skill}, which is explicitly "
            "requested in the job description."
        )
        for skill in matched[:4]
    ]
    if not strengths:
        strengths.append(
            f"Your resume shares {language_overlap}% of the job description's priority vocabulary; "
            "add concrete evidence for the role's named technical requirements."
        )

    risks = [
        f"{skill} appears in the job description but is not explicit in the resume."
        for skill in missing[:5]
    ]
    if not risks and job_skills:
        risks.append(
            "No major named-skill gap was detected; validate depth, recency, and measurable "
            "impact during interview preparation."
        )
    elif not job_skills:
        risks.append(
            "The job description contains few recognizable technical skills, so this score "
            "relies more heavily on language overlap."
        )

    explanation = (
        f"Fit is weighted 72% toward explicit skill coverage ({skill_coverage}%) and 28% "
        f"toward priority job-language overlap ({language_overlap}%). The analysis found "
        f"{len(matched)} matched and {len(missing)} missing named skills."
    )

    return CareerJobAnalysis(
        job_title=payload.job_title,
        company=payload.company,
        source_url=payload.source_url,
        fit_score=fit_score,
        skill_coverage=skill_coverage,
        language_overlap=language_overlap,
        matched_skills=matched,
        missing_skills=missing,
        resume_skills=resume_skills,
        priority_keywords=_priority_keywords(payload.job_description),
        strengths=strengths,
        risks=risks,
        interview_questions=_build_questions(payload, matched, missing),
        scoring_explanation=explanation,
    )


def _require_candidate(principal: AuthenticatedPrincipal) -> None:
    if Role.candidate not in principal.roles:
        raise HTTPException(status_code=403, detail="CareerOS is available to candidate accounts")


def _career_job_status(value: object) -> CareerJobStatus:
    if not isinstance(value, str) or value not in CAREER_JOB_STATUSES:
        raise RuntimeError("invalid CareerOS job status stored in database")
    return cast(CareerJobStatus, value)


def _save_resume_document(connection: Connection, resume_text: str) -> UUID:
    row = connection.execute(
        text(
            f"""
            INSERT INTO career_documents (
                user_id, kind, title, raw_text, content_sha256
            )
            VALUES ({_CURRENT_USER_SQL}, 'resume', 'Resume', :raw_text, :content_sha256)
            ON CONFLICT ON CONSTRAINT uq_career_documents_user_kind_sha256
            DO UPDATE SET title=EXCLUDED.title
            RETURNING id
            """
        ),
        {"raw_text": resume_text, "content_sha256": _sha256(resume_text)},
    ).mappings().one()
    return UUID(str(row["id"]))


def _find_or_create_job(
    connection: Connection,
    payload: CareerJobAnalysisInput,
) -> tuple[UUID, CareerJobStatus]:
    description_sha = _sha256(payload.job_description)
    params = {
        "job_title": payload.job_title,
        "company": payload.company,
        "source_url": payload.source_url,
        "job_description": payload.job_description,
        "description_sha": description_sha,
    }
    existing = connection.execute(
        text(
            f"""
            SELECT id, status
            FROM career_jobs
            WHERE user_id={_CURRENT_USER_SQL}
              AND job_description_sha256=:description_sha
              AND COALESCE(job_title, '')=COALESCE(:job_title, '')
              AND COALESCE(company, '')=COALESCE(:company, '')
            ORDER BY updated_at DESC
            LIMIT 1
            """
        ),
        params,
    ).mappings().one_or_none()

    if existing is not None:
        connection.execute(
            text(
                f"""
                UPDATE career_jobs
                SET source_url=COALESCE(:source_url, source_url),
                    job_description=:job_description,
                    last_analyzed_at=CURRENT_TIMESTAMP,
                    updated_at=CURRENT_TIMESTAMP
                WHERE id=:job_id
                  AND user_id={_CURRENT_USER_SQL}
                """
            ),
            {**params, "job_id": existing["id"]},
        )
        return UUID(str(existing["id"])), _career_job_status(existing["status"])

    created = connection.execute(
        text(
            f"""
            INSERT INTO career_jobs (
                user_id,
                job_title,
                company,
                source_url,
                job_description,
                job_description_sha256,
                last_analyzed_at
            )
            VALUES (
                {_CURRENT_USER_SQL},
                :job_title,
                :company,
                :source_url,
                :job_description,
                :description_sha,
                CURRENT_TIMESTAMP
            )
            RETURNING id, status
            """
        ),
        params,
    ).mappings().one()
    return UUID(str(created["id"])), _career_job_status(created["status"])


def _save_analysis(
    connection: Connection,
    *,
    job_id: UUID,
    document_id: UUID,
    analysis: CareerJobAnalysis,
) -> tuple[UUID, datetime]:
    row = connection.execute(
        text(
            f"""
            INSERT INTO career_job_analyses (
                user_id,
                job_id,
                document_id,
                scoring_version,
                fit_score,
                analysis
            )
            VALUES (
                {_CURRENT_USER_SQL},
                :job_id,
                :document_id,
                :scoring_version,
                :fit_score,
                CAST(:analysis AS jsonb)
            )
            RETURNING id, created_at
            """
        ),
        {
            "job_id": job_id,
            "document_id": document_id,
            "scoring_version": SCORING_VERSION,
            "fit_score": analysis.fit_score,
            "analysis": json.dumps(analysis.model_dump(mode="json")),
        },
    ).mappings().one()
    return UUID(str(row["id"])), row["created_at"]


def _summary_from_row(row: Mapping[str, Any]) -> CareerJobSummary:
    latest_analysis_value = row["latest_analysis"]
    latest_analysis = (
        latest_analysis_value if isinstance(latest_analysis_value, Mapping) else {}
    )
    return CareerJobSummary(
        id=UUID(str(row["id"])),
        job_title=row["job_title"],
        company=row["company"],
        source_url=row["source_url"],
        status=_career_job_status(row["status"]),
        latest_fit_score=row["latest_fit_score"],
        matched_skills=list(latest_analysis.get("matched_skills", [])),
        missing_skills=list(latest_analysis.get("missing_skills", [])),
        analysis_count=int(row["analysis_count"]),
        last_analyzed_at=row["last_analyzed_at"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


@router.post("/jobs/analyze", response_model=CareerSavedAnalysis)
def analyze_career_job(
    payload: CareerJobAnalysisInput,
    principal: Annotated[AuthenticatedPrincipal, Depends(authenticated_principal)],
    engine: DatabaseEngine,
) -> CareerSavedAnalysis:
    _require_candidate(principal)
    analysis = analyze_job(payload)
    with principal_transaction(engine, principal) as connection:
        document_id = _save_resume_document(connection, payload.resume_text)
        job_id, job_status = _find_or_create_job(connection, payload)
        analysis_id, created_at = _save_analysis(
            connection,
            job_id=job_id,
            document_id=document_id,
            analysis=analysis,
        )
    return CareerSavedAnalysis(
        **analysis.model_dump(),
        job_id=job_id,
        document_id=document_id,
        analysis_id=analysis_id,
        status=job_status,
        scoring_version=SCORING_VERSION,
        created_at=created_at,
    )


@router.get("/jobs", response_model=list[CareerJobSummary])
def list_career_jobs(
    principal: Annotated[AuthenticatedPrincipal, Depends(authenticated_principal)],
    engine: DatabaseEngine,
) -> list[CareerJobSummary]:
    _require_candidate(principal)
    with principal_transaction(engine, principal) as connection:
        rows = connection.execute(
            text(
                f"""
                SELECT
                    j.id,
                    j.job_title,
                    j.company,
                    j.source_url,
                    j.status,
                    j.last_analyzed_at,
                    j.created_at,
                    j.updated_at,
                    latest.fit_score AS latest_fit_score,
                    latest.analysis AS latest_analysis,
                    COALESCE(counts.analysis_count, 0) AS analysis_count
                FROM career_jobs j
                LEFT JOIN LATERAL (
                    SELECT a.fit_score, a.analysis
                    FROM career_job_analyses a
                    WHERE a.job_id=j.id
                      AND a.user_id={_CURRENT_USER_SQL}
                    ORDER BY a.created_at DESC
                    LIMIT 1
                ) latest ON TRUE
                LEFT JOIN LATERAL (
                    SELECT COUNT(*) AS analysis_count
                    FROM career_job_analyses a
                    WHERE a.job_id=j.id
                      AND a.user_id={_CURRENT_USER_SQL}
                ) counts ON TRUE
                WHERE j.user_id={_CURRENT_USER_SQL}
                ORDER BY COALESCE(j.last_analyzed_at, j.updated_at) DESC
                LIMIT 100
                """
            )
        ).mappings().all()
    return [_summary_from_row(row) for row in rows]


@router.patch("/jobs/{job_id}/status", response_model=CareerJobSummary)
def update_career_job_status(
    job_id: UUID,
    payload: CareerJobStatusInput,
    principal: Annotated[AuthenticatedPrincipal, Depends(authenticated_principal)],
    engine: DatabaseEngine,
) -> CareerJobSummary:
    _require_candidate(principal)
    with principal_transaction(engine, principal) as connection:
        updated = connection.execute(
            text(
                f"""
                UPDATE career_jobs
                SET status=:status, updated_at=CURRENT_TIMESTAMP
                WHERE id=:job_id
                  AND user_id={_CURRENT_USER_SQL}
                RETURNING id
                """
            ),
            {"job_id": job_id, "status": payload.status},
        ).scalar_one_or_none()
        if updated is None:
            raise HTTPException(status_code=404, detail="CareerOS job not found")

        row = connection.execute(
            text(
                f"""
                SELECT
                    j.id,
                    j.job_title,
                    j.company,
                    j.source_url,
                    j.status,
                    j.last_analyzed_at,
                    j.created_at,
                    j.updated_at,
                    latest.fit_score AS latest_fit_score,
                    latest.analysis AS latest_analysis,
                    COALESCE(counts.analysis_count, 0) AS analysis_count
                FROM career_jobs j
                LEFT JOIN LATERAL (
                    SELECT a.fit_score, a.analysis
                    FROM career_job_analyses a
                    WHERE a.job_id=j.id
                      AND a.user_id={_CURRENT_USER_SQL}
                    ORDER BY a.created_at DESC
                    LIMIT 1
                ) latest ON TRUE
                LEFT JOIN LATERAL (
                    SELECT COUNT(*) AS analysis_count
                    FROM career_job_analyses a
                    WHERE a.job_id=j.id
                      AND a.user_id={_CURRENT_USER_SQL}
                ) counts ON TRUE
                WHERE j.id=:job_id
                  AND j.user_id={_CURRENT_USER_SQL}
                """
            ),
            {"job_id": job_id},
        ).mappings().one()
    return _summary_from_row(row)
