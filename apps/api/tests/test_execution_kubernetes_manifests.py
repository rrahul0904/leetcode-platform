from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BOUNDARY = ROOT / "infra" / "kubernetes" / "execution-boundary.yaml"
CONTROLLER = ROOT / "infra" / "kubernetes" / "execution-controller.yaml"


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
    assert 'resources: ["pods/log"]' in manifest
    assert "allowPrivilegeEscalation: false" in manifest
    assert "readOnlyRootFilesystem: true" in manifest
    assert "seccompProfile:" in manifest
    assert "nodeSelector:" in manifest
    assert "workload: trusted-execution-control" in manifest
    assert "value: trusted-execution-control" in manifest
    assert "effect: NoSchedule" in manifest
