from __future__ import annotations

import sys
from pathlib import Path
from uuid import uuid4

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from publish_production_launch_catalog import (  # noqa: E402
    EXPECTED_LAUNCH_PACKAGES,
    launch_ids,
    require_bootstrap_authorization,
    validate_rights,
)
from rigor_api.content_sync import (  # noqa: E402
    discover_package_directories,
    load_package,
    validate_all,
)
from rigor_api.execution_capability import _capability  # noqa: E402

REQUESTED_HOSTNAME = (
    "skillforge-interactive-demo-bmbpowee0-rrahul0904-5013s-projects.vercel.app"
)


def test_production_launch_allowlist_is_exactly_the_first_party_launch_50() -> None:
    identifiers = launch_ids()

    assert EXPECTED_LAUNCH_PACKAGES == 50
    assert len(identifiers) == EXPECTED_LAUNCH_PACKAGES
    assert len(set(identifiers)) == EXPECTED_LAUNCH_PACKAGES
    assert len({identifier for identifier in identifiers if identifier.startswith("PY-")}) == 20
    assert len({identifier for identifier in identifiers if identifier.startswith("SQL-")}) == 10
    architecture_ids = {
        identifier
        for identifier in identifiers
        if not identifier.startswith(("PY-", "SQL-"))
    }
    assert len(architecture_ids) == 20
    assert {f"PY-{index:04d}" for index in range(1, 21)} <= identifiers
    assert {f"SQL-{index:04d}" for index in range(1, 11)} <= identifiers


def test_all_50_launch_packages_pass_release_validation_and_rights() -> None:
    identifiers = launch_ids()
    content_root = ROOT / "content"
    directories = {
        directory.name: directory for directory in discover_package_directories(content_root)
    }

    assert identifiers <= directories.keys()
    results = validate_all(content_root, set(identifiers))
    assert len(results) == EXPECTED_LAUNCH_PACKAGES
    assert [result.question_id for result in results if result.status == "invalid"] == []
    assert {validate_rights(directories[identifier]) for identifier in identifiers} == {
        "RIGOR-FIRST-PARTY-1.0"
    }


def test_launch_execution_availability_matches_real_content_contract() -> None:
    identifiers = launch_ids()
    content_root = ROOT / "content"
    directories = {
        directory.name: directory for directory in discover_package_directories(content_root)
    }
    availability: dict[str, str] = {}

    for identifier in sorted(identifiers):
        package = load_package(directories[identifier])
        capability = _capability(
            {
                "question_version_id": uuid4(),
                "structured_content": package.question.model_dump(mode="json"),
            }
        )
        availability[identifier] = capability.availability

    python_ids = {identifier for identifier in identifiers if identifier.startswith("PY-")}
    sql_ids = {identifier for identifier in identifiers if identifier.startswith("SQL-")}
    hosted_ids = identifiers - python_ids - sql_ids

    assert {identifier for identifier in python_ids if availability[identifier] == "runnable"} == (
        python_ids
    )
    assert {identifier for identifier in sql_ids if availability[identifier] == "runnable"} == sql_ids
    assert {identifier for identifier in hosted_ids if availability[identifier] == "hosted"} == (
        hosted_ids
    )


def test_production_launch_bootstrap_is_fail_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("RIGOR_PRODUCTION_LAUNCH_BOOTSTRAP_ENABLED", raising=False)
    monkeypatch.delenv("RIGOR_PRODUCTION_LAUNCH_BOOTSTRAP_REASON", raising=False)

    with pytest.raises(RuntimeError, match="only allowed"):
        require_bootstrap_authorization("local")

    with pytest.raises(RuntimeError, match="ENABLED=true"):
        require_bootstrap_authorization("production")

    monkeypatch.setenv("RIGOR_PRODUCTION_LAUNCH_BOOTSTRAP_ENABLED", "true")
    with pytest.raises(RuntimeError, match="must explain"):
        require_bootstrap_authorization("production")

    reason = "Initial audited first-party SkillForge production launch"
    monkeypatch.setenv("RIGOR_PRODUCTION_LAUNCH_BOOTSTRAP_REASON", reason)
    assert require_bootstrap_authorization("production") == reason


def test_release_workflow_preserves_exact_requested_hostname_contract() -> None:
    workflow = (ROOT / ".github" / "workflows" / "deploy-vercel-skillforge.yml").read_text(
        encoding="utf-8"
    )

    assert f"REQUESTED_CANONICAL_HOSTNAME: {REQUESTED_HOSTNAME}" in workflow
    assert f"REQUESTED_CANONICAL_URL: https://{REQUESTED_HOSTNAME}" in workflow
    assert "Assign the exact requested hostname without deleting the old deployment" in workflow
    assert "EXACT HOSTNAME BLOCKED BY VERCEL PLATFORM/API CONSTRAINT" in workflow
    assert "The old deployment was not deleted or released." in workflow


def test_release_workflow_targets_existing_project_and_never_skillsforge_ai() -> None:
    workflow = (ROOT / ".github" / "workflows" / "deploy-vercel-skillforge.yml").read_text(
        encoding="utf-8"
    )

    assert "VERCEL_PROJECT_ID: prj_fnbuYcKQeKrEq5Sax2uWdTg2SHqT" in workflow
    assert "VERCEL_PROJECT_NAME: skillforge-interactive-demo" in workflow
    assert "skillsforge-ai" not in workflow
