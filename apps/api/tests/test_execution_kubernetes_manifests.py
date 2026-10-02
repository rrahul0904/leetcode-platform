from __future__ import annotations

import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[3]
BOUNDARY = ROOT / "infra" / "kubernetes" / "execution-boundary.yaml"
CONTROLLER = ROOT / "infra" / "kubernetes" / "execution-controller.yaml"
STAGING_DEPLOY_SCRIPT = ROOT / "scripts" / "deploy_execution_staging.sh"


def test_execution_boundary_declares_runsc_and_default_deny() -> None:
    manifest = BOUNDARY.read_text(encoding="utf-8")

    assert "name: gvisor" in manifest
    assert "handler: runsc" in manifest
    assert 'rigor.io/gvisor: "true"' in manifest
    assert "automountServiceAccountToken: false" in manifest
    assert "name: default-deny-all" in manifest
    assert "ingress: []" in manifest
    assert "egress: []" in manifest
    assert "pod-security.kubernetes.io/enforce: restricted" in manifest


def test_controller_manifest_supplies_all_runtime_images_and_is_least_privileged() -> None:
    manifest = CONTROLLER.read_text(encoding="utf-8")

    for variable in (
        "RIGOR_PYTHON_RUNNER_IMAGE",
        "RIGOR_SQL_RUNNER_IMAGE",
        "RIGOR_SQL_POSTGRES_IMAGE",
    ):
        assert f"- name: {variable}" in manifest

    for key in (
        "python-runner-image",
        "sql-runner-image",
        "sql-postgres-image",
    ):
        assert f"key: {key}" in manifest

    assert 'resources: ["jobs"]' in manifest
    assert 'verbs: ["create", "get", "delete"]' in manifest
    assert 'resources: ["networkpolicies"]' not in manifest
    assert "trivy:ignore:KSV-0056" not in manifest
    assert 'resources: ["pods/log"]' in manifest
    assert "allowPrivilegeEscalation: false" in manifest
    assert "readOnlyRootFilesystem: true" in manifest
    assert "seccompProfile:" in manifest
    assert "nodeSelector:" in manifest
    assert "workload: trusted-execution-control" in manifest
    assert "value: trusted-execution-control" in manifest
    assert "effect: NoSchedule" in manifest


def test_staging_deploy_rejects_namespace_without_managed_default_deny() -> None:
    environment = os.environ.copy()
    environment.update(
        {
            "AWS_REGION": "us-east-1",
            "RIGOR_STAGING_EKS_CLUSTER": "test-cluster",
            "RIGOR_EXECUTION_QUEUE_URL": "https://sqs.us-east-1.amazonaws.com/123456789012/test",
            "RIGOR_STAGING_DATABASE_EXECUTOR_SECRET_ID": "test-secret",
            "RIGOR_EXECUTION_CONTROLLER_IMAGE": "controller@test@sha256:" + "a" * 64,
            "RIGOR_PYTHON_RUNNER_IMAGE": "python@test@sha256:" + "b" * 64,
            "RIGOR_SQL_RUNNER_IMAGE": "sql@test@sha256:" + "c" * 64,
            "RIGOR_SQL_POSTGRES_IMAGE": "postgres@test@sha256:" + "d" * 64,
            "RIGOR_STAGING_PROBE_IMAGE": "probe@test@sha256:" + "e" * 64,
            "RIGOR_EXECUTION_NAMESPACE": "custom-execution",
        }
    )
    result = subprocess.run(
        ["bash", str(STAGING_DEPLOY_SCRIPT)],
        capture_output=True,
        check=False,
        cwd=ROOT,
        env=environment,
        text=True,
    )

    assert result.returncode == 2
    assert "RIGOR_EXECUTION_NAMESPACE must be rigor-execution" in result.stderr
