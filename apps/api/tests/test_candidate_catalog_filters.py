from __future__ import annotations

from typing import cast

from fastapi.testclient import TestClient
from rigor_api.auth import LocalOIDCProvider
from rigor_api.main import app
from sqlalchemy import Engine

from test_published_catalog import cleanup_catalog_fixtures, seed_catalog_fixtures


def test_candidate_question_type_filter_uses_published_payload() -> None:
    with TestClient(app) as client:
        engine = cast(Engine, app.state.database_engine)
        provider = cast(LocalOIDCProvider, app.state.local_oidc_provider)
        seed_catalog_fixtures(engine)
        try:
            token = provider.issue_test_access_token("candidate", expires_in=900)
            headers = {"Authorization": f"Bearer {token}"}

            python_questions = client.get(
                "/api/v1/candidate/questions",
                headers=headers,
                params={"question_type": "python_coding"},
            )
            assert python_questions.status_code == 200
            assert python_questions.json()["total"] == 1
            assert python_questions.json()["items"][0]["slug"] == "candidate-safe-cache"

            sql_questions = client.get(
                "/api/v1/candidate/questions",
                headers=headers,
                params={"question_type": "sql_coding"},
            )
            assert sql_questions.status_code == 200
            assert sql_questions.json()["total"] == 0
        finally:
            cleanup_catalog_fixtures(engine)
