from __future__ import annotations

from uuid import UUID

import pytest

from rigor_api.sandbox_jobs import (
    SandboxConfigurationError,
    build_network_policy,
    build_python_job,
    sandbox_profile,
    validate_immutable_image_reference,
)


EXECUTION_ID = UUID("33333333-3333-3333-3333-333333333333")


def test_python_job_has_required_sandbox_controls() -> None:
    job = build_python_job(
        execution_id=EXECUTION_ID,
        namespace="rigor-execution",
        input_secret_name="execution-input-3333",
        runner_image="runner-python:3.13-v1",
    )

    spec = job["spec"]
    pod_spec = spec["template"]["spec"]  # type: ignore[index]
    container = pod_spec["containers"][0]

    assert spec["backoffLimit"] == 0  # type: ignore[index]
    assert spec["activeDeadlineSeconds"] == 20  # type: ignore[index]
    assert pod_spec["runtimeClassName"] == "gvisor"
    assert pod_spec["automountServiceAccountToken"] is False
    assert pod_spec["enableServiceLinks"] is False
    assert pod_spec["hostNetwork"] is False
    assert pod_spec["hostPID"] is False
    assert pod_spec["hostIPC"] is False
    assert container["securityContext"]["allowPrivilegeEscalation"] is False
    assert container["securityContext"]["readOnlyRootFilesystem"] is True
    assert container["securityContext"]["capabilities"] == {"drop": ["ALL"]}
    assert container["resources"]["limits"]["cpu"] == "1000m"
    assert container["resources"]["limits"]["memory"] == "512Mi"

    env_names = {entry["name"] for entry in container["env"]}
    assert "AWS_ACCESS_KEY_ID" not in env_names
    assert "AWS_SECRET_ACCESS_KEY" not in env_names
    assert "AWS_SESSION_TOKEN" not in env_names


def test_default_network_policy_denies_ingress_and_egress() -> None:
    policy = build_network_policy(
        execution_id=EXECUTION_ID,
        namespace="rigor-execution",
    )

    spec = policy["spec"]
    assert spec["policyTypes"] == ["Ingress", "Egress"]  # type: ignore[index]
    assert spec["ingress"] == []  # type: ignore[index]
    assert spec["egress"] == []  # type: ignore[index]


def test_runner_image_must_be_versioned_or_digest_pinned() -> None:
    with pytest.raises(SandboxConfigurationError):
        validate_immutable_image_reference("runner-python:latest")
    with pytest.raises(SandboxConfigurationError):
        validate_immutable_image_reference("runner-python:production")
    with pytest.raises(SandboxConfigurationError):
        validate_immutable_image_reference("runner-python")

    validate_immutable_image_reference("runner-python:3.13-v1")
    validate_immutable_image_reference("registry/runner@sha256:" + "a" * 64)


def test_candidate_cannot_select_sql_profile_for_python_job() -> None:
    assert sandbox_profile("sql-small").runtime.value == "sql"
    with pytest.raises(SandboxConfigurationError):
        build_python_job(
            execution_id=EXECUTION_ID,
            namespace="rigor-execution",
            input_secret_name="execution-input-3333",
            runner_image="runner-python:3.13-v1",
            profile_name="sql-small",
        )
