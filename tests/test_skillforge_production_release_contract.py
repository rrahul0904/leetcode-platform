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

REQUESTED_HOSTNAME = "skillforge-interactive-demo.vercel.app"
CLASS_PYTHON_HOSTED_IDS = {"PY-0001", "PY-0003", "PY-0004"}


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
    architecture_ids = identifiers - python_ids - sql_ids
    runnable_python_ids = python_ids - CLASS_PYTHON_HOSTED_IDS
    hosted_ids = architecture_ids | CLASS_PYTHON_HOSTED_IDS

    assert len(runnable_python_ids) == 17
    assert len(sql_ids) == 10
    assert len(hosted_ids) == 23
    assert {
        identifier
        for identifier in runnable_python_ids
        if availability[identifier] == "runnable"
    } == runnable_python_ids
    assert {
        identifier for identifier in sql_ids if availability[identifier] == "runnable"
    } == sql_ids
    assert {
        identifier for identifier in hosted_ids if availability[identifier] == "hosted"
    } == hosted_ids
    assert sum(value == "runnable" for value in availability.values()) == 27
    assert sum(value == "hosted" for value in availability.values()) == 23


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


def test_release_workflow_preserves_stable_production_domain_contract() -> None:
    workflow = (ROOT / ".github" / "workflows" / "deploy-vercel-skillforge.yml").read_text(
        encoding="utf-8"
    )

    assert f"REQUESTED_CANONICAL_HOSTNAME: {REQUESTED_HOSTNAME}" in workflow
    assert f"REQUESTED_CANONICAL_URL: https://{REQUESTED_HOSTNAME}" in workflow
    assert "vercel deploy --prebuilt --prod" in workflow
    assert "Verify production domain points to the new deployment" in workflow
    assert "No manual alias reassignment will be attempted" in workflow
    assert (
        "skillforge-interactive-demo-bmbpowee0-rrahul0904-5013s-projects.vercel.app"
        not in workflow
    )


def test_release_workflow_requires_controlled_production_boundary() -> None:
    workflow = (ROOT / ".github" / "workflows" / "deploy-vercel-skillforge.yml").read_text(
        encoding="utf-8"
    )
    trigger = workflow.split("permissions:", 1)[0]

    assert "workflow_dispatch:" in trigger
    assert "pull_request:" not in trigger
    assert "      - main" in trigger
    assert "      - agent/" not in trigger
    assert "environment: production" in workflow


def test_release_workflow_retains_exact_sha_certification_evidence() -> None:
    workflow = (ROOT / ".github" / "workflows" / "deploy-vercel-skillforge.yml").read_text(
        encoding="utf-8"
    )

    assert "RELEASE_SHA:" in workflow
    assert '--meta githubCommitSha="$RELEASE_SHA"' in workflow
    assert 'if [ "$deployment_sha" != "$RELEASE_SHA" ]; then' in workflow
    assert "production-release-evidence.json" in workflow
    assert "skillforge-production-certification-${{ env.RELEASE_SHA }}" in workflow
    assert "retention-days: 90" in workflow


def test_release_workflow_dispatches_ecs_with_immutable_sha_and_unique_correlation() -> None:
    release_workflow = (
        ROOT / ".github" / "workflows" / "deploy-vercel-skillforge.yml"
    ).read_text(encoding="utf-8")
    ecs_workflow = (ROOT / ".github" / "workflows" / "deploy-ecs.yml").read_text(
        encoding="utf-8"
    )

    assert '-f release_sha="$RELEASE_SHA"' in release_workflow
    assert '-f correlation_id="$ecs_correlation_id"' in release_workflow
    assert "displayTitle == env.ECS_RUN_NAME" in release_workflow
    assert ".headSha == env.RELEASE_SHA" not in release_workflow
    assert "release_sha:" in ecs_workflow
    assert "correlation_id:" in ecs_workflow
    assert "ref: ${{ env.RELEASE_SHA }}" in ecs_workflow
    assert '[[ ! "$RELEASE_SHA" =~ ^[0-9a-f]{40}$ ]]' in ecs_workflow
    assert 'actual_sha="$(git rev-parse HEAD)"' in ecs_workflow
    assert 'if [ "$actual_sha" != "$RELEASE_SHA" ]; then' in ecs_workflow
    assert ecs_workflow.count("IMAGE_TAG: ${{ env.RELEASE_SHA }}") == 2

    validate_input = ecs_workflow.index("Validate immutable release SHA input")
    checkout = ecs_workflow.index("- uses: actions/checkout")
    verify_checkout = ecs_workflow.index("Verify exact checked-out release commit")
    aws_credentials = ecs_workflow.index("Configure AWS credentials using GitHub OIDC")
    assert validate_input < checkout < verify_checkout < aws_credentials


def test_ci_concurrency_separates_push_and_pull_request_runs() -> None:
    ci = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    evidence = (
        ROOT / ".github" / "workflows" / "python-test-evidence.yml"
    ).read_text(encoding="utf-8")

    expected = "${{ github.event_name }}-${{ github.event.pull_request.number || github.ref_name }}"
    assert expected in ci
    assert expected in evidence


def test_release_workflow_targets_existing_project_and_never_skillsforge_ai() -> None:
    workflow = (ROOT / ".github" / "workflows" / "deploy-vercel-skillforge.yml").read_text(
        encoding="utf-8"
    )

    assert "VERCEL_PROJECT_ID: prj_fnbuYcKQeKrEq5Sax2uWdTg2SHqT" in workflow
    assert "VERCEL_PROJECT_NAME: skillforge-interactive-demo" in workflow
    assert "skillsforge-ai" not in workflow


def test_documented_production_migration_head_matches_release_contract() -> None:
    workflow = (ROOT / ".github" / "workflows" / "deploy-vercel-skillforge.yml").read_text(
        encoding="utf-8"
    )
    production_stack = (ROOT / "docs" / "SKILLFORGE_PRODUCTION_STACK.md").read_text(
        encoding="utf-8"
    )
    aws_deployment = (ROOT / "docs" / "skillforge-aws-deployment.md").read_text(
        encoding="utf-8"
    )

    expected_head = "20260918_0021"
    assert f"EXPECTED_ALEMBIC_HEAD: {expected_head}" in workflow
    assert expected_head in production_stack
    assert expected_head in aws_deployment
    assert "20260826_0017" not in production_stack
    assert "20260826_0017" not in aws_deployment


def test_production_web_defaults_never_point_to_loopback() -> None:
    production_env = (ROOT / "apps" / "web" / ".env.production").read_text(
        encoding="utf-8"
    )

    assert "NEXT_PUBLIC_RIGOR_API_URL=/api/backend" in production_env
    assert "localhost" not in production_env
    assert "127.0.0.1" not in production_env
    assert "0.0.0.0" not in production_env


def test_launch_week_control_record_keeps_external_release_gates_visible() -> None:
    launch_record = (ROOT / "docs" / "LAUNCH_WEEK_2026-09-27.md").read_text(
        encoding="utf-8"
    )

    assert "VERCEL_TOKEN" in launch_record
    assert "AWS_DEPLOY_ROLE_ARN" in launch_record
    assert "20260918_0021" in launch_record
    assert "skillforge-interactive-demo.vercel.app" in launch_record


def test_production_release_rejects_test_mode_identity_and_loopback_database() -> None:
    workflow = (ROOT / ".github" / "workflows" / "deploy-vercel-skillforge.yml").read_text(
        encoding="utf-8"
    )

    assert 'pk_live_*)' in workflow
    assert 'sk_live_*)' in workflow
    assert "Production requires a Clerk live publishable key" in workflow
    assert "Production requires a Clerk live secret key" in workflow
    assert "Refusing production release with localhost/loopback database" in workflow
    assert 'prefix="pk_live_"' in workflow


def test_production_csp_uses_verified_clerk_issuer() -> None:
    next_config = (ROOT / "apps" / "web" / "next.config.ts").read_text(
        encoding="utf-8"
    )
    release_workflow = (
        ROOT / ".github" / "workflows" / "deploy-vercel-skillforge.yml"
    ).read_text(encoding="utf-8")

    assert "RIGOR_CLERK_ISSUER" in next_config
    assert "const clerkOrigin = clerkFrontendOrigin(configuredClerkIssuer)" in next_config
    assert "${clerkOrigin}" in next_config
    assert 'set_env RIGOR_CLERK_ISSUER "$clerk_issuer"' in release_workflow
