from __future__ import annotations

from typing import cast
from uuid import uuid4

from fastapi.testclient import TestClient
from rigor_api.knowledge_store import import_knowledge_payload
from rigor_api.main import app
from sqlalchemy import Engine, text


def test_completed_knowledge_payload_is_not_imported_twice() -> None:
    nonce = uuid4().hex
    source_name = f"idempotency-test-{nonce}"
    canonical_key = f"test:{nonce}"
    slug = f"idempotency-{nonce}"
    source_path = f"questions/{nonce}.json"
    source_hash = nonce.ljust(64, "0")[:64]
    payload: dict[str, object] = {
        "source_name": source_name,
        "disposition": "external_reference_only",
        "files": [],
        "problems": [
            {
                "canonical_key": canonical_key,
                "external_id": nonce,
                "title": "Idempotency fixture",
                "slug": slug,
                "description": "A transaction-level import idempotency fixture.",
                "difficulty": "easy",
                "source_url": f"https://example.invalid/{nonce}",
                "topics": ["testing"],
                "source_name": source_name,
                "source_path": source_path,
                "source_hash": source_hash,
                "disposition": "external_reference_only",
            }
        ],
        "solutions": [],
        "companies": [],
        "system_design": [],
        "resources": [],
    }

    with TestClient(app):
        engine = cast(Engine, app.state.database_engine)
        first = import_knowledge_payload(engine, payload)
        second = import_knowledge_payload(engine, payload)

        assert first["status"] == "completed"
        assert second["status"] == "already_imported"
        assert second["import_id"] == first["import_id"]
        assert second["corpus_sha256"] == first["corpus_sha256"]
        assert second["counters"] == first["counters"]

        with engine.connect() as connection:
            problem_count = connection.execute(
                text("SELECT count(*) FROM knowledge_problems WHERE canonical_key=:key"),
                {"key": canonical_key},
            ).scalar_one()
            import_count = connection.execute(
                text(
                    """
                    SELECT count(*)
                    FROM knowledge_import_runs runs
                    JOIN knowledge_sources sources ON sources.id=runs.source_id
                    WHERE sources.source_name=:source_name
                      AND runs.corpus_sha256=:corpus_sha256
                      AND runs.status='completed'
                    """
                ),
                {
                    "source_name": source_name,
                    "corpus_sha256": first["corpus_sha256"],
                },
            ).scalar_one()

        assert problem_count == 1
        assert import_count == 1
