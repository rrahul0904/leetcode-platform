from __future__ import annotations

import io
import json
import zipfile
from copy import deepcopy
from typing import cast

import pytest
from content_fixtures import (
    malformed_unknown_field,
    python_question,
    sql_question,
    system_design_question,
)
from fastapi.testclient import TestClient
from rigor_api.auth import LocalOIDCProvider
from rigor_api.ingestion import IngestionError, SafeUploadParser
from rigor_api.main import app
from sqlalchemy import Engine, text


def _tokens(client: TestClient) -> tuple[dict[str, str], dict[str, str]]:
    provider = cast(LocalOIDCProvider, app.state.local_oidc_provider)
    administrator = provider.issue_test_access_token("platform-administrator", expires_in=900)
    candidate = provider.issue_test_access_token("candidate", expires_in=900)
    return (
        {"Authorization": f"Bearer {administrator}"},
        {"Authorization": f"Bearer {candidate}"},
    )


def _upload(
    client: TestClient,
    headers: dict[str, str],
    payload: object,
    *,
    filename: str = "questions.json",
    dry_run: bool = True,
):
    endpoint = (
        "/api/v1/admin/content/imports/validate" if dry_run else "/api/v1/admin/content/imports"
    )
    return client.post(
        endpoint,
        headers=headers,
        files={"file": (filename, json.dumps(payload), "application/json")},
    )


def test_original_python_sql_and_system_design_packages_pass_all_gates() -> None:
    with TestClient(app) as client:
        administrator, _ = _tokens(client)
        packages = (
            ("python.json", python_question("PY-9921"), "python_coding"),
            ("sql.json", sql_question("SQL-9921"), "sql_coding"),
            ("system-design.json", system_design_question("SD-9921"), "system_design"),
        )
        for filename, package, question_type in packages:
            response = _upload(client, administrator, package, filename=filename)
            assert response.status_code == 200
            report = response.json()
            assert report["status"] == "completed"
            assert report["accepted_count"] == 1
            assert report["rejected_count"] == 0
            assert report["rollback_available"] is False
            item = report["items"][0]
            assert item["question_version_id"] is None
            stages = {stage["stage"]: stage for stage in item["stages"]}
            assert stages["schema_parsing"]["metrics"]["question_type"] == question_type
            assert stages["license_validation"]["status"] == "passed"
            assert stages["provenance_validation"]["status"] == "passed"
            assert stages["executable_solution_validation"]["status"] == "passed"
            assert stages["draft_creation"]["status"] == "skipped"


def test_malformed_rights_and_batch_duplicates_are_rejected_per_item() -> None:
    with TestClient(app) as client:
        administrator, _ = _tokens(client)

        unknown = _upload(client, administrator, malformed_unknown_field())
        assert unknown.status_code == 200
        assert unknown.json()["status"] == "failed"
        assert "Extra inputs are not permitted" in " ".join(unknown.json()["items"][0]["errors"])

        missing_rights = python_question("PY-9922")
        del missing_rights["license"]
        rights = _upload(client, administrator, missing_rights)
        assert rights.status_code == 200
        assert rights.json()["rejected_count"] == 1
        assert any("license" in error for error in rights.json()["items"][0]["errors"])

        duplicate = python_question("PY-9923")
        duplicates = _upload(client, administrator, [duplicate, deepcopy(duplicate)])
        assert duplicates.status_code == 200
        assert duplicates.json()["accepted_count"] == 1
        assert duplicates.json()["rejected_count"] == 1
        second_errors = duplicates.json()["items"][1]["errors"]
        assert any("duplicate ID in import" in error for error in second_errors)
        assert any("duplicate slug in import" in error for error in second_errors)


def test_real_import_is_generated_idempotent_candidate_hidden_and_rollbackable() -> None:
    with TestClient(app) as client:
        administrator, candidate = _tokens(client)
        package = python_question("PY-9924")

        forbidden = _upload(client, candidate, package, dry_run=False)
        assert forbidden.status_code == 403

        first = _upload(client, administrator, package, dry_run=False)
        assert first.status_code == 200
        first_report = first.json()
        assert first_report["accepted_count"] == 1
        assert first_report["rollback_available"] is True
        version_id = first_report["items"][0]["question_version_id"]
        assert version_id

        second = _upload(client, administrator, package, dry_run=False)
        assert second.status_code == 200
        assert second.json()["items"][0]["question_version_id"] == version_id

        engine = cast(Engine, app.state.database_engine)
        with engine.connect() as connection:
            state = connection.execute(
                text("SELECT state::text FROM question_versions WHERE id=:version_id"),
                {"version_id": version_id},
            ).scalar_one()
        assert state == "generated"

        candidate_catalog = client.get(
            "/api/v1/questions", headers=candidate, params={"query": package["title"]}
        )
        assert candidate_catalog.status_code == 200
        assert all(item["id"] != package["id"] for item in candidate_catalog.json()["items"])

        assert second.json()["rollback_available"] is False
        noop_rollback = client.post(
            f"/api/v1/admin/content/imports/{second.json()['import_id']}/rollback",
            headers=administrator,
        )
        assert noop_rollback.status_code == 409

        rollback = client.post(
            f"/api/v1/admin/content/imports/{first_report['import_id']}/rollback",
            headers=administrator,
        )
        assert rollback.status_code == 200
        assert rollback.json()["rolled_back_versions"] == 1
        repeated = client.post(
            f"/api/v1/admin/content/imports/{first_report['import_id']}/rollback",
            headers=administrator,
        )
        assert repeated.status_code == 200
        assert repeated.json()["rolled_back_versions"] == 0


def test_zip_slip_and_unexpected_python_executables_are_blocked() -> None:
    parser = SafeUploadParser()
    unsafe = io.BytesIO()
    with zipfile.ZipFile(unsafe, "w") as archive:
        archive.writestr("../question.json", "{}")
    with pytest.raises(IngestionError, match="unsafe path"):
        parser.parse("unsafe.zip", unsafe.getvalue())

    executable = io.BytesIO()
    with zipfile.ZipFile(executable, "w") as archive:
        archive.writestr("package/question.json", "{}")
        archive.writestr("package/run_me.py", "print('unexpected')")
    with pytest.raises(IngestionError, match="Unexpected executable Python file"):
        parser.parse("executable.zip", executable.getvalue())


def test_content_factory_caps_batches_requires_track_intent_and_records_traces() -> None:
    with TestClient(app) as client:
        administrator, candidate = _tokens(client)
        batch = {
            "questions": [python_question("PY-9925")],
            "prompt_version": "factory-v1",
            "model_provider": "deterministic-test-provider",
            "model_identifier": "original-fixture-v1",
            "dry_run": True,
        }
        forbidden = client.post(
            "/api/v1/admin/content/factory/batches", headers=candidate, json=batch
        )
        assert forbidden.status_code == 403

        accepted = client.post(
            "/api/v1/admin/content/factory/batches", headers=administrator, json=batch
        )
        assert accepted.status_code == 200
        assert accepted.json()["source_method"] == "generation"
        assert accepted.json()["accepted_count"] == 1
        assert accepted.json()["dry_run"] is True

        engine = cast(Engine, app.state.database_engine)
        with engine.connect() as connection:
            trace = (
                connection.execute(
                    text(
                        "SELECT manifest_id, stage, prompt_version, model_provider "
                        "FROM generation_traces gt JOIN content_import_items i "
                        "ON i.id=gt.import_item_id WHERE i.import_id=:import_id"
                    ),
                    {"import_id": accepted.json()["import_id"]},
                )
                .mappings()
                .one()
            )
        assert dict(trace) == {
            "manifest_id": "PY-9925",
            "stage": "validated_draft_generation",
            "prompt_version": "factory-v1",
            "model_provider": "deterministic-test-provider",
        }

        mixed = deepcopy(batch)
        mixed["questions"] = [python_question("PY-9926"), sql_question("SQL-9926")]
        mixed_response = client.post(
            "/api/v1/admin/content/factory/batches", headers=administrator, json=mixed
        )
        assert mixed_response.status_code == 422
        assert "one primary track" in mixed_response.json()["message"]

        too_large = deepcopy(batch)
        too_large["questions"] = [python_question(f"PY-{index:04d}") for index in range(9930, 9941)]
        oversized = client.post(
            "/api/v1/admin/content/factory/batches", headers=administrator, json=too_large
        )
        assert oversized.status_code == 422
