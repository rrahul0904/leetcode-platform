from __future__ import annotations

import re
from collections import Counter
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from .auth import authenticated_principal
from .schemas import AuthenticatedPrincipal, Role

router = APIRouter(prefix="/api/v1/career", tags=["career-os"])


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


def _contains_alias(text: str, alias: str) -> bool:
    # Word-like boundaries prevent short aliases such as JS/TS/ML from matching inside
    # unrelated words while still supporting punctuation-heavy skills such as CI/CD.
    pattern = rf"(?<![a-z0-9]){re.escape(alias.casefold())}(?![a-z0-9])"
    return re.search(pattern, text) is not None


def _extract_skills(value: str) -> list[str]:
    text = _normalize(value)
    return [
        display_name
        for display_name, aliases in SKILL_ALIASES.items()
        if any(_contains_alias(text, alias) for alias in aliases)
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
    # Compare against the most informative recurring JD vocabulary, not every prose word.
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
    # Skills are the stronger signal when the JD contains explicit technology requirements.
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


@router.post("/jobs/analyze", response_model=CareerJobAnalysis)
def analyze_career_job(
    payload: CareerJobAnalysisInput,
    principal: Annotated[AuthenticatedPrincipal, Depends(authenticated_principal)],
) -> CareerJobAnalysis:
    _require_candidate(principal)
    return analyze_job(payload)
