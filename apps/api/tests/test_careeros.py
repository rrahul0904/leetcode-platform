from __future__ import annotations

from typing import cast

from fastapi.testclient import TestClient
from rigor_api.auth import LocalOIDCProvider
from rigor_api.careeros import CareerJobAnalysisInput, analyze_job
from rigor_api.main import app


def test_job_analysis_is_explainable_and_generates_interview_pack() -> None:
    result = analyze_job(
        CareerJobAnalysisInput(
            job_title="Senior Data Platform Engineer",
            company="Example Co",
            resume_text=(
                "Senior data engineer with Python, SQL, PostgreSQL, AWS, Docker and dbt experience. "
                "Built reliable ETL data pipelines and production APIs with measurable latency reductions."
            ),
            job_description=(
                "We need a senior data platform engineer with Python, SQL, AWS, Docker, Kubernetes, "
                "dbt, Kafka, data engineering, system design and CI/CD experience. Own scalable data pipelines."
            ),
        )
    )

    assert 0 <= result.fit_score <= 100
    assert result.skill_coverage > 0
    assert "Python" in result.matched_skills
    assert "SQL" in result.matched_skills
    assert "Kubernetes" in result.missing_skills
    assert "Kafka" in result.missing_skills
    assert len(result.interview_questions) >= 5
    assert any(question.category == "gap" for question in result.interview_questions)
    assert "72%" in result.scoring_explanation


def test_job_analysis_handles_nontechnical_job_language() -> None:
    result = analyze_job(
        CareerJobAnalysisInput(
            resume_text=(
                "Program manager who led cross-functional planning, stakeholder communication, "
                "roadmaps, launches, metrics, and customer research across multiple teams."
            ),
            job_description=(
                "Lead cross-functional planning and stakeholder communication. Own roadmaps, launch "
                "execution, customer research, metrics, and executive updates across multiple teams."
            ),
        )
    )

    assert result.matched_skills == []
    assert result.missing_skills == []
    assert result.fit_score == result.language_overlap
    assert len(result.priority_keywords) > 0
    assert len(result.interview_questions) == 2


def test_career_route_requires_candidate_role() -> None:
    with TestClient(app) as client:
        provider = cast(LocalOIDCProvider, app.state.local_oidc_provider)
        payload = {
            "resume_text": (
                "Backend engineer with Python, PostgreSQL, Docker, AWS and distributed systems experience."
            ),
            "job_description": (
                "Backend engineer role requiring Python, PostgreSQL, Docker, AWS, Kubernetes and system design."
            ),
        }

        candidate = provider.issue_test_access_token("candidate", expires_in=900)
        response = client.post(
            "/api/v1/career/jobs/analyze",
            headers={"Authorization": f"Bearer {candidate}"},
            json=payload,
        )
        assert response.status_code == 200
        assert "fit_score" in response.json()

        author = provider.issue_test_access_token("author", expires_in=900)
        forbidden = client.post(
            "/api/v1/career/jobs/analyze",
            headers={"Authorization": f"Bearer {author}"},
            json=payload,
        )
        assert forbidden.status_code == 403
