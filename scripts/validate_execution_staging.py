from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from contextlib import suppress
from dataclasses import dataclass
from typing import cast
from uuid import uuid4

NAMESPACE = os.getenv("RIGOR_EXECUTION_NAMESPACE", "rigor-execution")
CONTEXT = os.getenv("RIGOR_STAGING_KUBE_CONTEXT", "")
PROBE_IMAGE = os.getenv("RIGOR_STAGING_PROBE_IMAGE", "")
TIMEOUT_SECONDS = int(os.getenv("RIGOR_STAGING_VALIDATION_TIMEOUT_SECONDS", "90"))

JsonObject = dict[str, object]


class ValidationError(RuntimeError):
    pass


@dataclass(frozen=True)
class CommandResult:
    stdout: str
    stderr: str


def run(*args: str, input_text: str | None = None) -> CommandResult:
    command = ["kubectl"]
    if CONTEXT:
        command.extend(["--context", CONTEXT])
    command.extend(args)
    completed = subprocess.run(
        command,
        input=input_text,
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    if completed.returncode != 0:
        raise ValidationError(
            f"Command failed ({' '.join(command)}): {completed.stderr.strip()}"
        )
    return CommandResult(completed.stdout, completed.stderr)


def resource_json(*args: str) -> JsonObject:
    value: object = json.loads(run(*args, "-o", "json").stdout)
    if not isinstance(value, dict):
        raise ValidationError("kubectl returned a non-object resource.")
    return cast(JsonObject, value)


def object_field(value: object, field: str) -> JsonObject:
    if not isinstance(value, dict):
        raise ValidationError(f"Kubernetes field {field!r} is not an object.")
    return cast(JsonObject, value)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValidationError(message)


def validate_static_cluster_contract() -> None:
    runtime = resource_json("get", "runtimeclass", "gvisor")
    require(runtime.get("handler") == "runsc", "RuntimeClass gvisor is not backed by runsc.")

    namespace = resource_json("get", "namespace", NAMESPACE)
    metadata = object_field(namespace.get("metadata"), "metadata")
    labels = object_field(metadata.get("labels"), "metadata.labels")
    require(
        labels.get("rigor.io/trust-plane") == "untrusted-execution",
        "Execution namespace trust-plane label is missing.",
    )
    require(
        labels.get("pod-security.kubernetes.io/enforce") == "restricted",
        "Execution namespace does not enforce restricted Pod Security.",
    )

    service_account = resource_json(
        "-n",
        NAMESPACE,
        "get",
        "serviceaccount",
        "candidate-execution",
    )
    require(
        service_account.get("automountServiceAccountToken") is False,
        "Candidate ServiceAccount must disable token automount.",
    )

    policy = resource_json("-n", NAMESPACE, "get", "networkpolicy", "default-deny-all")
    spec = object_field(policy.get("spec"), "networkpolicy.spec")
    require(spec.get("ingress") == [], "Default deny policy has ingress exceptions.")
    require(spec.get("egress") == [], "Default deny policy has egress exceptions.")
    policy_types = spec.get("policyTypes")
    require(
        isinstance(policy_types, list) and set(policy_types) == {"Ingress", "Egress"},
        "Default deny policy must cover ingress and egress.",
    )


def probe_manifest(name: str) -> dict[str, object]:
    return {
        "apiVersion": "v1",
        "kind": "Pod",
        "metadata": {
            "name": name,
            "namespace": NAMESPACE,
            "labels": {
                "app.kubernetes.io/part-of": "rigor",
                "rigor.io/validation": "runsc",
            },
        },
        "spec": {
            "runtimeClassName": "gvisor",
            "serviceAccountName": "candidate-execution",
            "automountServiceAccountToken": False,
            "enableServiceLinks": False,
            "restartPolicy": "Never",
            "hostNetwork": False,
            "hostPID": False,
            "hostIPC": False,
            "nodeSelector": {
                "rigor.io/gvisor": "true",
                "workload": "untrusted-execution",
            },
            "tolerations": [
                {
                    "key": "workload",
                    "operator": "Equal",
                    "value": "untrusted-execution",
                    "effect": "NoSchedule",
                }
            ],
            "containers": [
                {
                    "name": "probe",
                    "image": PROBE_IMAGE,
                    "imagePullPolicy": "IfNotPresent",
                    "command": ["/bin/sh", "-ceu", "dmesg | head -n 80; sleep 2"],
                    "securityContext": {
                        "allowPrivilegeEscalation": False,
                        "readOnlyRootFilesystem": True,
                        "runAsNonRoot": True,
                        "capabilities": {"drop": ["ALL"]},
                        "seccompProfile": {"type": "RuntimeDefault"},
                    },
                    "resources": {
                        "requests": {"cpu": "25m", "memory": "32Mi"},
                        "limits": {"cpu": "100m", "memory": "64Mi"},
                    },
                }
            ],
        },
    }


def wait_for_terminal_pod(name: str) -> JsonObject:
    deadline = time.monotonic() + TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        pod = resource_json("-n", NAMESPACE, "get", "pod", name)
        status = object_field(pod.get("status"), "pod.status")
        phase = status.get("phase")
        if phase == "Succeeded":
            return pod
        if phase == "Failed":
            raise ValidationError(f"gVisor probe Pod failed: {name}")
        time.sleep(1)
    raise ValidationError(f"Timed out waiting for gVisor probe Pod {name}.")


def validate_live_runsc() -> None:
    require(PROBE_IMAGE != "", "RIGOR_STAGING_PROBE_IMAGE is required.")
    require(
        "@sha256:" in PROBE_IMAGE,
        "RIGOR_STAGING_PROBE_IMAGE must be immutable and pinned by digest.",
    )
    name = f"rigor-runsc-proof-{uuid4().hex[:10]}"
    manifest = json.dumps(probe_manifest(name), separators=(",", ":"))
    try:
        run("apply", "-f", "-", input_text=manifest)
        pod = wait_for_terminal_pod(name)
        spec = object_field(pod.get("spec"), "pod.spec")
        require(
            spec.get("runtimeClassName") == "gvisor",
            "Probe Pod did not use gvisor RuntimeClass.",
        )
        node_name = str(spec.get("nodeName") or "")
        require(node_name != "", "Probe Pod was not scheduled to a node.")
        node = resource_json("get", "node", node_name)
        node_metadata = object_field(node.get("metadata"), "node.metadata")
        node_labels = object_field(node_metadata.get("labels"), "node.metadata.labels")
        require(
            node_labels.get("rigor.io/gvisor") == "true",
            "Probe node lacks rigor.io/gvisor=true.",
        )
        require(
            node_labels.get("workload") == "untrusted-execution",
            "Probe node is not dedicated to untrusted execution.",
        )
        logs = run("-n", NAMESPACE, "logs", name, "-c", "probe").stdout
        require(
            "Starting gVisor" in logs,
            "Live probe did not produce gVisor dmesg evidence; runsc is NOT proven.",
        )
    finally:
        with suppress(ValidationError, subprocess.TimeoutExpired):
            run("-n", NAMESPACE, "delete", "pod", name, "--ignore-not-found=true")


def main() -> int:
    try:
        validate_static_cluster_contract()
        validate_live_runsc()
    except (ValidationError, subprocess.TimeoutExpired, json.JSONDecodeError) as exc:
        print(f"STAGING VALIDATION FAILED: {exc}", file=sys.stderr)
        return 1
    print("STAGING VALIDATED: live restricted execution Pod proved gVisor/runsc.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
