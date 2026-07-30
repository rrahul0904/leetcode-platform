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

EXECUTION_NODE_SELECTOR = {"workload": "untrusted-execution"}
EXECUTION_TOLERATIONS = [
    {
        "key": "workload",
        "operator": "Equal",
        "value": "untrusted-execution",
        "effect": "NoSchedule",
    }
]


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


def _pod_security_context() -> dict[str, object]:
    return {
        "runAsNonRoot": True,
        "seccompProfile": {"type": "RuntimeDefault"},
    }


def _container_security_context(*, read_only_root: bool = True) -> dict[str, object]:
    return {
        "allowPrivilegeEscalation": False,
        "readOnlyRootFilesystem": read_only_root,
        "runAsNonRoot": True,
        "capabilities": {"drop": ["ALL"]},
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
        "metadata": {"name": name, "namespace": namespace, "labels": labels},
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
                    "nodeSelector": EXECUTION_NODE_SELECTOR,
                    "tolerations": EXECUTION_TOLERATIONS,
                    "securityContext": {
                        **_pod_security_context(),
                        "runAsUser": 65532,
                        "runAsGroup": 65532,
                        "fsGroup": 65532,
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
                            "securityContext": _container_security_context(),
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
                                {"name": "workspace", "mountPath": "/workspace"},
                            ],
                        }
                    ],
                    "volumes": [
                        {
                            "name": "execution-input",
                            "secret": {"secretName": input_secret_name, "defaultMode": 256},
                        },
                        {
                            "name": "workspace",
                            "emptyDir": {"sizeLimit": profile.ephemeral_storage_limit},
                        },
                    ],
                },
            },
        },
    }


def _secret_env(name: str, secret_name: str, key: str) -> dict[str, object]:
    return {
        "name": name,
        "valueFrom": {"secretKeyRef": {"name": secret_name, "key": key}},
    }


def build_sql_job(
    *,
    execution_id: UUID,
    namespace: str,
    input_secret_name: str,
    runner_image: str,
    postgres_image: str,
    profile_name: str = "sql-small",
) -> dict[str, object]:
    """Build one gVisor Job containing a SQL runner and disposable PostgreSQL sidecar."""

    validate_immutable_image_reference(runner_image)
    validate_immutable_image_reference(postgres_image)
    profile = sandbox_profile(profile_name)
    if profile.runtime is not SandboxRuntime.sql:
        raise SandboxConfigurationError("SQL execution requires a SQL sandbox profile.")

    labels = {
        "app.kubernetes.io/name": "rigor-sql-runner",
        "app.kubernetes.io/component": "candidate-execution",
        "rigor.io/execution-id": str(execution_id),
        "rigor.io/sandbox-profile": profile.name,
    }
    name = sandbox_job_name(execution_id)
    runner_env: list[dict[str, object]] = [
        {"name": "HOME", "value": "/workspace"},
        {"name": "TMPDIR", "value": "/workspace/tmp"},
        {"name": "RIGOR_SQL_HOST", "value": "127.0.0.1"},
        {"name": "RIGOR_SQL_PORT", "value": "5432"},
        {"name": "RIGOR_SQL_DATABASE", "value": "rigor_execution"},
        {"name": "RIGOR_SQL_OWNER_USER", "value": "rigor_sql_owner"},
        {"name": "RIGOR_SQL_CANDIDATE_USER", "value": "rigor_sql_candidate"},
        _secret_env("RIGOR_SQL_OWNER_PASSWORD", input_secret_name, "owner-password"),
        _secret_env("RIGOR_SQL_CANDIDATE_PASSWORD", input_secret_name, "candidate-password"),
    ]
    postgres_env: list[dict[str, object]] = [
        {"name": "POSTGRES_DB", "value": "rigor_execution"},
        {"name": "POSTGRES_USER", "value": "rigor_sql_owner"},
        _secret_env("POSTGRES_PASSWORD", input_secret_name, "owner-password"),
        {"name": "PGDATA", "value": "/var/lib/postgresql/data/pgdata"},
    ]

    return {
        "apiVersion": "batch/v1",
        "kind": "Job",
        "metadata": {"name": name, "namespace": namespace, "labels": labels},
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
                    "nodeSelector": EXECUTION_NODE_SELECTOR,
                    "tolerations": EXECUTION_TOLERATIONS,
                    "securityContext": _pod_security_context(),
                    "initContainers": [
                        {
                            "name": "postgres",
                            "image": postgres_image,
                            "imagePullPolicy": "IfNotPresent",
                            "restartPolicy": "Always",
                            "env": postgres_env,
                            "securityContext": {
                                **_container_security_context(),
                                "runAsUser": 999,
                                "runAsGroup": 999,
                            },
                            "resources": {
                                "requests": {"cpu": "100m", "memory": "128Mi"},
                                "limits": {
                                    "cpu": profile.cpu_limit,
                                    "memory": profile.memory_limit,
                                    "ephemeral-storage": profile.ephemeral_storage_limit,
                                },
                            },
                            "volumeMounts": [
                                {"name": "postgres-data", "mountPath": "/var/lib/postgresql/data"},
                                {"name": "postgres-run", "mountPath": "/var/run/postgresql"},
                                {"name": "postgres-tmp", "mountPath": "/tmp"},
                            ],
                        }
                    ],
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
                            ],
                            "env": runner_env,
                            "securityContext": {
                                **_container_security_context(),
                                "runAsUser": 65532,
                                "runAsGroup": 65532,
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
                                {"name": "workspace", "mountPath": "/workspace"},
                            ],
                        }
                    ],
                    "volumes": [
                        {
                            "name": "execution-input",
                            "secret": {"secretName": input_secret_name, "defaultMode": 256},
                        },
                        {
                            "name": "workspace",
                            "emptyDir": {"sizeLimit": "32Mi"},
                        },
                        {
                            "name": "postgres-data",
                            "emptyDir": {"sizeLimit": profile.ephemeral_storage_limit},
                        },
                        {"name": "postgres-run", "emptyDir": {"sizeLimit": "8Mi"}},
                        {"name": "postgres-tmp", "emptyDir": {"sizeLimit": "16Mi"}},
                    ],
                },
            },
        },
    }
