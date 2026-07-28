from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID


class SandboxRuntime(StrEnum):
    python = "python"
    sql = "sql"


@dataclass(frozen=True)
class SandboxProfile:
    name: str
    runtime: SandboxRuntime
    cpu_request: str
    cpu_limit: str
    memory_request: str
    memory_limit: str
    ephemeral_storage_limit: str
    execution_timeout_seconds: int
    job_deadline_seconds: int


SANDBOX_PROFILES: dict[str, SandboxProfile] = {
    "python-small": SandboxProfile(
        name="python-small",
        runtime=SandboxRuntime.python,
        cpu_request="100m",
        cpu_limit="1000m",
        memory_request="128Mi",
        memory_limit="512Mi",
        ephemeral_storage_limit="32Mi",
        execution_timeout_seconds=10,
        job_deadline_seconds=20,
    ),
    "python-large": SandboxProfile(
        name="python-large",
        runtime=SandboxRuntime.python,
        cpu_request="250m",
        cpu_limit="2000m",
        memory_request="256Mi",
        memory_limit="1024Mi",
        ephemeral_storage_limit="64Mi",
        execution_timeout_seconds=15,
        job_deadline_seconds=30,
    ),
    "sql-small": SandboxProfile(
        name="sql-small",
        runtime=SandboxRuntime.sql,
        cpu_request="250m",
        cpu_limit="1000m",
        memory_request="256Mi",
        memory_limit="768Mi",
        ephemeral_storage_limit="128Mi",
        execution_timeout_seconds=10,
        job_deadline_seconds=30,
    ),
    "sql-large": SandboxProfile(
        name="sql-large",
        runtime=SandboxRuntime.sql,
        cpu_request="500m",
        cpu_limit="2000m",
        memory_request="512Mi",
        memory_limit="1536Mi",
        ephemeral_storage_limit="256Mi",
        execution_timeout_seconds=20,
        job_deadline_seconds=45,
    ),
}


class SandboxConfigurationError(ValueError):
    pass


def sandbox_profile(name: str) -> SandboxProfile:
    try:
        return SANDBOX_PROFILES[name]
    except KeyError as exc:
        raise SandboxConfigurationError("Unknown server-controlled sandbox profile.") from exc


def validate_immutable_image_reference(image: str) -> None:
    normalized = image.strip().casefold()
    if not normalized or normalized.endswith(":latest") or normalized.endswith(":production"):
        raise SandboxConfigurationError("Sandbox image must use an immutable version or digest.")
    if "@sha256:" not in normalized and ":" not in normalized.rsplit("/", 1)[-1]:
        raise SandboxConfigurationError("Sandbox image must include a version tag or digest.")


def sandbox_job_name(execution_id: UUID) -> str:
    return f"execution-{execution_id}"


def build_network_policy(*, execution_id: UUID, namespace: str) -> dict[str, object]:
    labels = {"rigor.io/execution-id": str(execution_id)}
    return {
        "apiVersion": "networking.k8s.io/v1",
        "kind": "NetworkPolicy",
        "metadata": {
            "name": f"deny-{sandbox_job_name(execution_id)}",
            "namespace": namespace,
        },
        "spec": {
            "podSelector": {"matchLabels": labels},
            "policyTypes": ["Ingress", "Egress"],
            "ingress": [],
            "egress": [],
        },
    }


def build_python_job(
    *,
    execution_id: UUID,
    namespace: str,
    input_secret_name: str,
    runner_image: str,
    profile_name: str = "python-small",
) -> dict[str, object]:
    validate_immutable_image_reference(runner_image)
    profile = sandbox_profile(profile_name)
    if profile.runtime is not SandboxRuntime.python:
        raise SandboxConfigurationError("Python execution requires a Python sandbox profile.")

    labels = {
        "app.kubernetes.io/name": "rigor-python-runner",
        "app.kubernetes.io/component": "candidate-execution",
        "rigor.io/execution-id": str(execution_id),
        "rigor.io/sandbox-profile": profile.name,
    }
    name = sandbox_job_name(execution_id)

    return {
        "apiVersion": "batch/v1",
        "kind": "Job",
        "metadata": {
            "name": name,
            "namespace": namespace,
            "labels": labels,
        },
        "spec": {
            "backoffLimit": 0,
            "ttlSecondsAfterFinished": 120,
            "activeDeadlineSeconds": profile.job_deadline_seconds,
            "template": {
                "metadata": {"labels": labels},
                "spec": {
                    "runtimeClassName": "gvisor",
                    "serviceAccountName": "candidate-execution",
                    "restartPolicy": "Never",
                    "automountServiceAccountToken": False,
                    "enableServiceLinks": False,
                    "hostNetwork": False,
                    "hostPID": False,
                    "hostIPC": False,
                    "securityContext": {
                        "runAsNonRoot": True,
                        "runAsUser": 65532,
                        "runAsGroup": 65532,
                        "fsGroup": 65532,
                        "seccompProfile": {"type": "RuntimeDefault"},
                    },
                    "containers": [
                        {
                            "name": "runner",
                            "image": runner_image,
                            "imagePullPolicy": "IfNotPresent",
                            "args": [
                                "--execution-id",
                                str(execution_id),
                                "--input",
                                "/run/rigor/input/request.json",
                                "--timeout-seconds",
                                str(profile.execution_timeout_seconds),
                            ],
                            "env": [
                                {"name": "HOME", "value": "/workspace"},
                                {"name": "TMPDIR", "value": "/workspace/tmp"},
                            ],
                            "securityContext": {
                                "allowPrivilegeEscalation": False,
                                "readOnlyRootFilesystem": True,
                                "runAsNonRoot": True,
                                "capabilities": {"drop": ["ALL"]},
                            },
                            "resources": {
                                "requests": {
                                    "cpu": profile.cpu_request,
                                    "memory": profile.memory_request,
                                },
                                "limits": {
                                    "cpu": profile.cpu_limit,
                                    "memory": profile.memory_limit,
                                    "ephemeral-storage": profile.ephemeral_storage_limit,
                                },
                            },
                            "volumeMounts": [
                                {
                                    "name": "execution-input",
                                    "mountPath": "/run/rigor/input",
                                    "readOnly": True,
                                },
                                {
                                    "name": "workspace",
                                    "mountPath": "/workspace",
                                },
                            ],
                        }
                    ],
                    "volumes": [
                        {
                            "name": "execution-input",
                            "secret": {
                                "secretName": input_secret_name,
                                "defaultMode": 256,
                            },
                        },
                        {
                            "name": "workspace",
                            "emptyDir": {
                                "sizeLimit": profile.ephemeral_storage_limit,
                            },
                        },
                    ],
                },
            },
        },
    }
