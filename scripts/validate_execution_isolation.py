from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from typing import cast
from uuid import uuid4

NAMESPACE = os.getenv("RIGOR_EXECUTION_NAMESPACE", "rigor-execution")
CONTEXT = os.getenv("RIGOR_STAGING_KUBE_CONTEXT", "")
PROBE_IMAGE = os.getenv("RIGOR_STAGING_PROBE_IMAGE", "")
TIMEOUT_SECONDS = int(os.getenv("RIGOR_STAGING_VALIDATION_TIMEOUT_SECONDS", "90"))
OPTIONAL_TARGETS = os.getenv("RIGOR_STAGING_BLOCKED_TARGETS", "")

AWS_ENV_NAMES = {
    "AWS_ACCESS_KEY_ID",
    "AWS_SECRET_ACCESS_KEY",
    "AWS_SESSION_TOKEN",
    "AWS_WEB_IDENTITY_TOKEN_FILE",
    "AWS_ROLE_ARN",
    "AWS_CONTAINER_CREDENTIALS_RELATIVE_URI",
    "AWS_CONTAINER_CREDENTIALS_FULL_URI",
}

JsonObject = dict[str, object]


class ValidationError(RuntimeError):
    pass


@dataclass(frozen=True)
class CommandResult:
    returncode: int
    stdout: str
    stderr: str


def kubectl(*args: str, input_text: str | None = None, check: bool = True) -> CommandResult:
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
    result = CommandResult(completed.returncode, completed.stdout, completed.stderr)
    if check and result.returncode != 0:
        raise ValidationError(
            f"Command failed ({' '.join(command)}): {result.stderr.strip()}"
        )
    return result


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValidationError(message)


def json_object(raw: str, label: str) -> JsonObject:
    value: object = json.loads(raw)
    if not isinstance(value, dict):
        raise ValidationError(f"{label} is not a JSON object.")
    return cast(JsonObject, value)


def object_field(value: object, field: str) -> JsonObject:
    if not isinstance(value, dict):
        raise ValidationError(f"Kubernetes field {field!r} is not an object.")
    return cast(JsonObject, value)


def probe_manifest(name: str) -> dict[str, object]:
    return {
        "apiVersion": "v1",
        "kind": "Pod",
        "metadata": {
            "name": name,
            "namespace": NAMESPACE,
            "labels": {
                "app.kubernetes.io/part-of": "rigor",
                "rigor.io/validation": "adversarial",
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
                    "command": ["/bin/sh", "-ceu", "sleep 300"],
                    "env": [
                        {"name": "PYTHONDONTWRITEBYTECODE", "value": "1"},
                        {"name": "PYTHONUNBUFFERED", "value": "1"},
                    ],
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


def wait_running(name: str) -> None:
    deadline = time.monotonic() + TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        raw = kubectl("-n", NAMESPACE, "get", "pod", name, "-o", "json").stdout
        pod = json_object(raw, "probe Pod")
        status = object_field(pod.get("status"), "pod.status")
        phase = status.get("phase")
        if phase == "Running":
            return
        if phase == "Failed":
            raise ValidationError("Adversarial probe Pod failed before validation.")
        time.sleep(1)
    raise ValidationError("Timed out waiting for adversarial probe Pod.")


def exec_probe(name: str, *command: str, check: bool = True) -> CommandResult:
    return kubectl(
        "-n",
        NAMESPACE,
        "exec",
        name,
        "-c",
        "probe",
        "--",
        *command,
        check=check,
    )


def validate_runtime(name: str) -> None:
    result = exec_probe(name, "dmesg")
    require("Starting gVisor" in result.stdout, "Live Pod did not prove gVisor via dmesg.")


def validate_credentials(name: str) -> None:
    environment = exec_probe(name, "env").stdout.splitlines()
    names = {line.split("=", 1)[0] for line in environment if "=" in line}
    exposed = sorted(names.intersection(AWS_ENV_NAMES))
    require(not exposed, f"AWS credential-provider environment is exposed: {exposed}")

    token_check = exec_probe(
        name,
        "/bin/sh",
        "-ceu",
        "test ! -r /var/run/secrets/kubernetes.io/serviceaccount/token",
        check=False,
    )
    require(token_check.returncode == 0, "Kubernetes service-account token is readable.")


def validate_filesystem(name: str) -> None:
    result = exec_probe(
        name,
        "/bin/sh",
        "-ceu",
        "touch /rigor-root-write-probe >/dev/null 2>&1 && exit 9 || exit 0",
        check=False,
    )
    require(result.returncode == 0, "Candidate container root filesystem is writable.")


def python_connect_script(host: str, port: int) -> str:
    return (
        "import socket,sys;"
        "s=socket.socket();s.settimeout(2);"
        f"target=({host!r},{port});"
        "ok=False;"
        "\ntry:\n s.connect(target); ok=True\nexcept OSError:\n pass\nfinally:\n s.close()\n"
        "sys.exit(9 if ok else 0)"
    )


def assert_blocked(name: str, host: str, port: int, label: str) -> None:
    result = exec_probe(
        name,
        "python3",
        "-c",
        python_connect_script(host, port),
        check=False,
    )
    require(result.returncode == 0, f"Candidate sandbox reached forbidden target {label}.")


def validate_network(name: str) -> None:
    assert_blocked(name, "169.254.169.254", 80, "AWS IMDS")
    assert_blocked(name, "1.1.1.1", 443, "Internet")
    assert_blocked(name, "kubernetes.default.svc", 443, "Kubernetes API")

    dns = exec_probe(
        name,
        "python3",
        "-c",
        (
            "import socket,sys;"
            "\ntry:\n socket.getaddrinfo('example.com',443); sys.exit(9)"
            "\nexcept OSError:\n sys.exit(0)"
        ),
        check=False,
    )
    require(dns.returncode == 0, "Candidate sandbox resolved public DNS under deny-all policy.")

    for item in filter(None, (part.strip() for part in OPTIONAL_TARGETS.split(","))):
        host, separator, raw_port = item.rpartition(":")
        require(
            separator == ":" and host != "",
            f"Invalid blocked target {item!r}; use host:port.",
        )
        try:
            port = int(raw_port)
        except ValueError as exc:
            raise ValidationError(f"Invalid port in blocked target {item!r}.") from exc
        require(1 <= port <= 65535, f"Invalid port in blocked target {item!r}.")
        assert_blocked(name, host, port, item)


def main() -> int:
    try:
        require(PROBE_IMAGE != "", "RIGOR_STAGING_PROBE_IMAGE is required.")
        require("@sha256:" in PROBE_IMAGE, "Probe image must be pinned by digest.")
        name = f"rigor-adversarial-{uuid4().hex[:10]}"
        try:
            kubectl("apply", "-f", "-", input_text=json.dumps(probe_manifest(name)))
            wait_running(name)
            validate_runtime(name)
            validate_credentials(name)
            validate_filesystem(name)
            validate_network(name)
        finally:
            kubectl(
                "-n",
                NAMESPACE,
                "delete",
                "pod",
                name,
                "--ignore-not-found=true",
                check=False,
            )
    except (ValidationError, subprocess.TimeoutExpired, json.JSONDecodeError) as exc:
        print(f"ADVERSARIAL VALIDATION FAILED: {exc}", file=sys.stderr)
        return 1
    print(
        "ADVERSARIAL STAGING VALIDATED: runtime, credential, filesystem, "
        "and network probes passed."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
