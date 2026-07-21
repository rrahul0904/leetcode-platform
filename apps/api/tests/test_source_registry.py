from __future__ import annotations

from typing import cast

from fastapi.testclient import TestClient
from rigor_api.auth import LocalOIDCProvider
from rigor_api.main import app
from sqlalchemy import Engine, text

TEST_DOMAIN = "authorized-content.example"


def cleanup_source(engine: Engine) -> None:
    with engine.begin() as connection:
        source_id = connection.execute(
            text("SELECT id FROM source_registry WHERE canonical_domain=:domain"),
            {"domain": TEST_DOMAIN},
        ).scalar_one_or_none()
        if source_id:
            connection.execute(
                text("DELETE FROM external_question_references WHERE source_id=:source_id"),
                {"source_id": source_id},
            )
            connection.execute(
                text("DELETE FROM audit_events WHERE resource_id=:resource_id"),
                {"resource_id": str(source_id)},
            )
            connection.execute(
                text("DELETE FROM source_registry WHERE id=:source_id"),
                {"source_id": source_id},
            )


def test_source_review_incremental_sync_external_separation_and_coverage() -> None:
    with TestClient(app) as client:
        engine = cast(Engine, app.state.database_engine)
        provider = cast(LocalOIDCProvider, app.state.local_oidc_provider)
        cleanup_source(engine)
        administrator = provider.issue_test_access_token("platform-administrator", expires_in=900)
        candidate = provider.issue_test_access_token("candidate", expires_in=900)
        admin_headers = {"Authorization": f"Bearer {administrator}"}
        candidate_headers = {"Authorization": f"Bearer {candidate}"}

        forbidden = client.get("/api/v1/admin/sources", headers=candidate_headers)
        assert forbidden.status_code == 403

        created = client.post(
            "/api/v1/admin/sources",
            headers=admin_headers,
            json={
                "source_name": "Authorized Content Example",
                "canonical_domain": f"https://{TEST_DOMAIN}/ignored-path",
                "source_category": "partner-feed",
                "discovery_method": "administrator-submission",
                "access_method": "official-api",
                "estimated_content_volume": 100,
                "priority": 80,
            },
        )
        assert created.status_code == 200
        source_id = created.json()["source_id"]
        assert created.json()["coverage_level"] == "DISCOVERY_ONLY"
        assert created.json()["connector_status"] == "unreviewed"

        premature_sync = client.post(
            f"/api/v1/admin/sources/{source_id}/sync",
            headers=admin_headers,
            json={"sync_mode": "incremental", "references": []},
        )
        assert premature_sync.status_code == 409

        invalid_rights = client.put(
            f"/api/v1/admin/sources/{source_id}/review",
            headers=admin_headers,
            json={
                "rights_status": "metadata_permitted",
                "coverage_level": "PARTNER_LICENSED_FULL_CONTENT",
                "collection_mode": "official-api",
                "connector_status": "approved",
                "connector_type": "official-partner-api",
                "connector_configuration": {},
                "review_notes": "Full content was not licensed, so approval must be rejected.",
            },
        )
        assert invalid_rights.status_code == 422

        reviewed = client.put(
            f"/api/v1/admin/sources/{source_id}/review",
            headers=admin_headers,
            json={
                "rights_status": "metadata_permitted",
                "coverage_level": "METADATA_ONLY",
                "collection_mode": "official-api",
                "connector_status": "approved",
                "connector_type": "official-metadata-api",
                "connector_configuration": {"rate_limit_per_minute": 30},
                "review_notes": "Official terms permit public metadata and canonical links only.",
            },
        )
        assert reviewed.status_code == 200
        assert reviewed.json()["last_reviewed_at"] is not None

        first_sync = client.post(
            f"/api/v1/admin/sources/{source_id}/sync",
            headers=admin_headers,
            json={
                "sync_mode": "initial_backfill",
                "cursor_after": {"page": 2},
                "complete_snapshot": True,
                "references": [
                    {
                        "source_external_id": "alpha",
                        "canonical_url": f"https://{TEST_DOMAIN}/questions/alpha",
                        "title": "Public Metadata Alpha",
                        "abstract": "A permitted high-level competency description.",
                        "difficulty": "advanced",
                        "topic_metadata": ["distributed-systems"],
                        "patterns": ["replication"],
                        "competency_slugs": ["distributed-systems", "reliability"],
                    },
                    {
                        "source_external_id": "beta",
                        "canonical_url": f"https://{TEST_DOMAIN}/questions/beta",
                        "title": "Public Metadata Beta",
                        "abstract": "A second permitted high-level competency description.",
                        "difficulty": "staff",
                        "topic_metadata": ["reliability"],
                        "patterns": ["failure-recovery"],
                        "competency_slugs": ["reliability"],
                    },
                ],
            },
        )
        assert first_sync.status_code == 200
        assert first_sync.json()["created_count"] == 2

        references = client.get(
            "/api/v1/external-references",
            headers=candidate_headers,
            params={"source_id": source_id},
        )
        assert references.status_code == 200
        assert references.json()["total"] == 2
        assert all("problem_statement" not in item for item in references.json()["items"])
        assert all("reference_solution" not in item for item in references.json()["items"])
        assert references.json()["items"][0]["competency_slugs"]
        assert references.json()["items"][0]["patterns"]

        filtered = client.get(
            "/api/v1/external-references",
            headers=candidate_headers,
            params={"source_id": source_id, "difficulty": "advanced"},
        )
        assert filtered.status_code == 200
        assert filtered.json()["total"] == 1
        competency_filtered = client.get(
            "/api/v1/external-references",
            headers=candidate_headers,
            params={"source_id": source_id, "competency": "reliability"},
        )
        assert competency_filtered.status_code == 200
        assert competency_filtered.json()["total"] == 2

        facets = client.get("/api/v1/external-reference-facets", headers=candidate_headers)
        assert facets.status_code == 200
        assert any(item["value"] == source_id for item in facets.json()["sources"])
        assert any(item["value"] == "reliability" for item in facets.json()["competencies"])

        summary = client.get("/api/v1/practice/summary", headers=candidate_headers)
        assert summary.status_code == 200
        assert summary.json()["external_references"] >= 2
        assert "planned_questions" not in summary.json()
        assert any(item["source_id"] == source_id for item in summary.json()["source_counts"])

        assert client.get(
            "/api/v1/admin/catalog/status", headers=candidate_headers
        ).status_code == 403
        catalog_status = client.get("/api/v1/admin/catalog/status", headers=admin_headers)
        assert catalog_status.status_code == 200
        assert any(item["source_id"] == source_id for item in catalog_status.json())

        second_sync = client.post(
            f"/api/v1/admin/sources/{source_id}/sync",
            headers=admin_headers,
            json={
                "sync_mode": "incremental",
                "cursor_before": {"page": 2},
                "cursor_after": {"page": 3},
                "complete_snapshot": True,
                "references": [
                    {
                        "source_external_id": "alpha",
                        "canonical_url": f"https://{TEST_DOMAIN}/questions/alpha",
                        "title": "Public Metadata Alpha Updated",
                        "abstract": "A permitted high-level competency description.",
                        "difficulty": "advanced",
                        "topic_metadata": ["distributed-systems"],
                        "patterns": ["replication"],
                        "competency_slugs": ["distributed-systems", "reliability"],
                    }
                ],
            },
        )
        assert second_sync.status_code == 200
        assert second_sync.json()["updated_count"] == 1
        assert second_sync.json()["unavailable_count"] == 1

        coverage = client.get("/api/v1/admin/coverage", headers=admin_headers)
        assert coverage.status_code == 200
        assert coverage.json()["growth_model"] == "continuous_unbounded"
        assert coverage.json()["foundation_manifest_entries"] == 1350
        assert coverage.json()["external_references"] >= 2
        assert coverage.json()["approved_sources"] >= 1
        assert "target_questions" not in coverage.json()

        with engine.connect() as connection:
            assert (
                connection.execute(
                    text(
                        """
                    SELECT count(*) FROM audit_events
                    WHERE resource_id=:source_id AND action IN (
                        'source.registered', 'source.reviewed', 'source.synchronized'
                    )
                    """
                    ),
                    {"source_id": source_id},
                ).scalar_one()
                == 4
            )
        cleanup_source(engine)
