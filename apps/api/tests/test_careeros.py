from __future__ import annotations

from typing import cast

from fastapi.testclient import TestClient
from rigor_api.auth import LOCAL_IDENTITIES, LocalIdentity, LocalOIDCProvider
from rigor_api.careeros import CareerJobAnalysisInput, analyze_job
from rigor_api.main import app
from rigor_api.schemas import Role
from sqlalchemy import Engine, text

SECOND_IDENTITY_KEY = "career-candidate-b"
SECOND_SUBJECT = "local-career-candidate-b"


def cleanup_candidate(engine: Engine, subject: str) -> None:
    with engine.begin() as connection:
        user_id = connection.execute(
            text("SELECT id FROM users WHERE identity_subject=:subject"),
            {"subject": subject},
        ).scalar_one_or_none()
        if user_id is not None:
            connection.execute(
                text("DELETE FROM audit_events WHERE actor_user_id=:user_id"),
                {"user_id": user_id},
            )
            connection.execute(
                text("DELETE FROM users WHERE id=:user_id"),
                {"user_id": user_id},
            )


def install_second_candidate() -> None:
    LOCAL_IDENTITIES[SECOND_IDENTITY_KEY] = LocalIdentity(
        SECOND_SUBJECT,
        "career-candidate-b@rigor.test",
        "Career Candidate B",
        (Role.candidate,),
    )


def test_job_analysis_is_explainable_and_generates_interview_pack() -> None:
    result = analyze_job(
        CareerJobAnalysisInput(
            job_title="Senior Data Platform Engineer",
            company="Example Co",
            resume_text=(
                "Senior data engineer with Python, SQL, PostgreSQL, AWS, Docker and dbt "
                "experience. Built reliable ETL data pipelines and production APIs with "
                "measurable latency reductions."
            ),
            job_description=(
                "We need a senior data platform engineer with Python, SQL, AWS, Docker, "
                "Kubernetes, dbt, Kafka, data engineering, system design and CI/CD experience. "
                "Own scalable data pipelines."
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
                "Lead cross-functional planning and stakeholder communication. Own roadmaps, "
                "launch execution, customer research, metrics, and executive updates across "
                "multiple teams."
            ),
        )
    )

    assert result.matched_skills == []
    assert result.missing_skills == []
    assert result.fit_score == result.language_overlap
    assert len(result.priority_keywords) > 0
    assert len(result.interview_questions) == 2


def test_career_job_history_is_persistent_deduplicated_and_rls_isolated() -> None:
    with TestClient(app) as client:
        engine = cast(Engine, app.state.database_engine)
        provider = cast(LocalOIDCProvider, app.state.local_oidc_provider)
        cleanup_candidate(engine, "local-candidate")
        cleanup_candidate(engine, SECOND_SUBJECT)
        install_second_candidate()
        try:
            payload = {
                "job_title": "Backend Engineer",
                "company": "Example Co",
                "resume_text": (
                    "Backend engineer with Python, PostgreSQL, Docker, AWS and distributed "
                    "systems experience delivering production APIs."
                ),
                "job_description": (
                    "Backend engineer role requiring Python, PostgreSQL, Docker, AWS, "
                    "Kubernetes and system design for reliable production services."
                ),
            }
            token_a = provider.issue_test_access_token("candidate", expires_in=900)
            token_b = provider.issue_test_access_token(SECOND_IDENTITY_KEY, expires_in=900)
            headers_a = {"Authorization": f"Bearer {token_a}"}
            headers_b = {"Authorization": f"Bearer {token_b}"}

            first = client.post(
                "/api/v1/career/jobs/analyze",
                headers=headers_a,
                json=payload,
            )
            assert first.status_code == 200
            first_body = first.json()
            assert first_body["status"] == "saved"
            assert first_body["scoring_version"] == "deterministic-v1"
            assert first_body["job_id"]
            assert first_body["analysis_id"]
            assert first_body["document_id"]

            second = client.post(
                "/api/v1/career/jobs/analyze",
                headers=headers_a,
                json=payload,
            )
            assert second.status_code == 200
            second_body = second.json()
            assert second_body["job_id"] == first_body["job_id"]
            assert second_body["document_id"] == first_body["document_id"]
            assert second_body["analysis_id"] != first_body["analysis_id"]

            jobs_a = client.get("/api/v1/career/jobs", headers=headers_a)
            assert jobs_a.status_code == 200
            assert len(jobs_a.json()) == 1
            assert jobs_a.json()[0]["analysis_count"] == 2
            assert jobs_a.json()[0]["latest_fit_score"] == second_body["fit_score"]

            jobs_b = client.get("/api/v1/career/jobs", headers=headers_b)
            assert jobs_b.status_code == 200
            assert jobs_b.json() == []

            foreign_update = client.patch(
                f"/api/v1/career/jobs/{first_body['job_id']}/status",
                headers=headers_b,
                json={"status": "applied"},
            )
            assert foreign_update.status_code == 404

            updated = client.patch(
                f"/api/v1/career/jobs/{first_body['job_id']}/status",
                headers=headers_a,
                json={"status": "applied"},
            )
            assert updated.status_code == 200
            assert updated.json()["status"] == "applied"

            author = provider.issue_test_access_token("author", expires_in=900)
            forbidden = client.get(
                "/api/v1/career/jobs",
                headers={"Authorization": f"Bearer {author}"},
            )
            assert forbidden.status_code == 403
        finally:
            LOCAL_IDENTITIES.pop(SECOND_IDENTITY_KEY, None)
            cleanup_candidate(engine, "local-candidate")
            cleanup_candidate(engine, SECOND_SUBJECT)
