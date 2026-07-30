from __future__ import annotations

from uuid import UUID

import pytest

from rigor_api.sandbox_jobs import (
    SandboxConfigurationError,
    build_network_policy,
    build_python_job,
    build_sql_job,
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
    assert pod_spec["serviceAccountName"] == "candidate-execution"
    assert pod_spec["automountServiceAccountToken"] is False
    assert pod_spec["enableServiceLinks"] is False
    assert pod_spec["hostNetwork"] is False
    assert pod_spec["hostPID"] is False
    assert pod_spec["hostIPC"] is False
    assert pod_spec["nodeSelector"] == {"workload": "untrusted-execution"}
    assert pod_spec["tolerations"] == [
        {
            "key": "workload",
            "operator": "Equal",
            "value": "untrusted-execution",
            "effect": "NoSchedule",
        }
    ]
    assert container["securityContext"]["allowPrivilegeEscalation"] is False
    assert container["securityContext"]["readOnlyRootFilesystem"] is True
    assert container["securityContext"]["capabilities"] == {"drop": ["ALL"]}
    assert container["resources"]["limits"]["cpu"] == "1000m"
    assert container["resources"]["limits"]["memory"] == "512Mi"

    env_names = {entry["name"] for entry in container["env"]}
    assert "AWS_ACCESS_KEY_ID" not in env_names
    assert "AWS_SECRET_ACCESS_KEY" not in env_names
    assert "AWS_SESSION_TOKEN" not in env_names


def test_sql_job_uses_disposable_postgres_sidecar_with_same_isolation_boundary() -> None:
    job = build_sql_job(
        execution_id=EXECUTION_ID,
        namespace="rigor-execution",
        input_secret_name="execution-input-3333",
        runner_image="runner-sql:postgresql18-v1",
        postgres_image="postgres:18.1-bookworm",
    )

    spec = job["spec"]
    pod_spec = spec["template"]["spec"]  # type: ignore[index]
    runner = pod_spec["containers"][0]
    postgres = pod_spec["initContainers"][0]

    assert spec["backoffLimit"] == 0  # type: ignore[index]
    assert spec["activeDeadlineSeconds"] == 30  # type: ignore[index]
    assert pod_spec["runtimeClassName"] == "gvisor"
    assert pod_spec["serviceAccountName"] == "candidate-execution"
    assert pod_spec["automountServiceAccountToken"] is False
    assert pod_spec["enableServiceLinks"] is False
    assert pod_spec["hostNetwork"] is False
    assert pod_spec["hostPID"] is False
    assert pod_spec["hostIPC"] is False
    assert pod_spec["nodeSelector"] == {"workload": "untrusted-execution"}

    assert postgres["name"] == "postgres"
    assert postgres["restartPolicy"] == "Always"
    assert postgres["securityContext"]["allowPrivilegeEscalation"] is False
    assert postgres["securityContext"]["readOnlyRootFilesystem"] is True
    assert postgres["securityContext"]["capabilities"] == {"drop": ["ALL"]}

    assert runner["name"] == "runner"
    assert runner["securityContext"]["allowPrivilegeEscalation"] is False
    assert runner["securityContext"]["readOnlyRootFilesystem"] is True
    assert runner["securityContext"]["capabilities"] == {"drop": ["ALL"]}

    runner_env = {entry["name"]: entry for entry in runner["env"]}
    postgres_env = {entry["name"]: entry for entry in postgres["env"]}
    for secret_name in ("RIGOR_SQL_OWNER_PASSWORD", "RIGOR_SQL_CANDIDATE_PASSWORD"):
        assert "secretKeyRef" in runner_env[secret_name]["valueFrom"]
    assert "secretKeyRef" in postgres_env["POSTGRES_PASSWORD"]["valueFrom"]

    for env_name in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN"):
        assert env_name not in runner_env
        assert env_name not in postgres_env

    volume_names = {volume["name"] for volume in pod_spec["volumes"]}
    assert "postgres-data" in volume_names
    assert "execution-input" in volume_names


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


def test_candidate_cannot_cross_runtime_profiles() -> None:
    assert sandbox_profile("sql-small").runtime.value == "sql"
    with pytest.raises(SandboxConfigurationError):
        build_python_job(
            execution_id=EXECUTION_ID,
            namespace="rigor-execution",
            input_secret_name="execution-input-3333",
            runner_image="runner-python:3.13-v1",
            profile_name="sql-small",
        )
    with pytest.raises(SandboxConfigurationError):
        build_sql_job(
            execution_id=EXECUTION_ID,
            namespace="rigor-execution",
            input_secret_name="execution-input-3333",
            runner_image="runner-sql:postgresql18-v1",
            postgres_image="postgres:18.1-bookworm",
            profile_name="python-small",
        )
