from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from publish_production_launch_catalog import (  # noqa: E402
    EXPECTED_LAUNCH_PACKAGES,
    launch_ids,
    require_bootstrap_authorization,
)

REQUESTED_HOSTNAME = (
    "skillforge-interactive-demo-bmbpowee0-rrahul0904-5013s-projects.vercel.app"
)


def test_production_launch_allowlist_is_exactly_the_first_party_launch_50() -> None:
    identifiers = launch_ids()

    assert EXPECTED_LAUNCH_PACKAGES == 50
    assert len(identifiers) == EXPECTED_LAUNCH_PACKAGES
    assert len(set(identifiers)) == EXPECTED_LAUNCH_PACKAGES
    assert {identifier.split("-", 1)[0] for identifier in identifiers} >= {
        "PY",
        "SQL",
        "SD",
    }


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
