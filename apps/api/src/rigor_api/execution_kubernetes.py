from __future__ import annotations

import json
import os
import secrets
import ssl
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, cast
from urllib import error, parse, request
from uuid import UUID

from .sandbox_jobs import (
    build_network_policy,
    build_python_job,
    build_sql_job,
    sandbox_job_name,
)

MAX_KUBERNETES_RESPONSE_BYTES = 512 * 1024


class KubernetesExecutionError(RuntimeError):
    pass


@dataclass(frozen=True)
class SandboxHandle:
    execution_id: UUID
    namespace: str
    job_name: str
    input_secret_name: str
    network_policy_name: str


@dataclass(frozen=True)
class SandboxObservation:
    state: str
    logs: str | None = None
    reason: str | None = None


class SandboxExecutor(Protocol):
    def create_python_execution(
        self,
        *,
        execution_id: UUID,
        request_payload: dict[str, object],
        profile_name: str,
    ) -> SandboxHandle: ...

    def create_sql_execution(
        self,
        *,
        execution_id: UUID,
        request_payload: dict[str, object],
        profile_name: str,
    ) -> SandboxHandle: ...

    def observe(self, handle: SandboxHandle) -> SandboxObservation: ...

    def cleanup(self, handle: SandboxHandle) -> None: ...


@dataclass(frozen=True)
class KubernetesApiConfig:
    api_url: str
    bearer_token: str
    ca_file: str | None
    namespace: str
    runner_image: str
    sql_runner_image: str
    sql_postgres_image: str

    @classmethod
    def discover(cls) -> KubernetesApiConfig:
        configured_url = os.getenv("RIGOR_KUBERNETES_API_URL")
        host = os.getenv("KUBERNETES_SERVICE_HOST")
        port = os.getenv("KUBERNETES_SERVICE_PORT_HTTPS", "443")
        api_url = configured_url or (f"https://{host}:{port}" if host else "")
        if not api_url.startswith("https://"):
            raise KubernetesExecutionError("Trusted dispatcher requires an HTTPS Kubernetes API.")

        configured_token = os.getenv("RIGOR_KUBERNETES_BEARER_TOKEN")
        token_file = Path(
            os.getenv(
                "RIGOR_KUBERNETES_TOKEN_FILE",
                "/var/run/secrets/kubernetes.io/serviceaccount/token",
            )
        )
        if configured_token:
            token = configured_token
        else:
            try:
                token = token_file.read_text(encoding="utf-8").strip()
            except OSError as exc:
                raise KubernetesExecutionError(
                    "Trusted dispatcher Kubernetes credential is unavailable."
                ) from exc
        if not token:
            raise KubernetesExecutionError("Trusted dispatcher Kubernetes credential is empty.")

        ca_file = os.getenv(
            "RIGOR_KUBERNETES_CA_FILE",
            "/var/run/secrets/kubernetes.io/serviceaccount/ca.crt",
        )
        if not Path(ca_file).exists():
            ca_file = None
        namespace = os.getenv("RIGOR_EXECUTION_NAMESPACE", "rigor-execution")
        runner_image = os.getenv("RIGOR_PYTHON_RUNNER_IMAGE", "")
        sql_runner_image = os.getenv("RIGOR_SQL_RUNNER_IMAGE", "")
        sql_postgres_image = os.getenv("RIGOR_SQL_POSTGRES_IMAGE", "")
        if not runner_image:
            raise KubernetesExecutionError("RIGOR_PYTHON_RUNNER_IMAGE is required.")
        if not sql_runner_image:
            raise KubernetesExecutionError("RIGOR_SQL_RUNNER_IMAGE is required.")
        if not sql_postgres_image:
            raise KubernetesExecutionError("RIGOR_SQL_POSTGRES_IMAGE is required.")
        return cls(
            api_url=api_url.rstrip("/"),
            bearer_token=token,
            ca_file=ca_file,
            namespace=namespace,
            runner_image=runner_image,
            sql_runner_image=sql_runner_image,
            sql_postgres_image=sql_postgres_image,
        )


@dataclass(frozen=True)
class KubernetesResponse:
    status: int
    body: bytes


class KubernetesTransport(Protocol):
    def request(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str],
        body: bytes | None,
        timeout_seconds: float,
    ) -> KubernetesResponse: ...


class UrllibKubernetesTransport:
    def __init__(self, ca_file: str | None) -> None:
        self._context = (
            ssl.create_default_context(cafile=ca_file)
            if ca_file
            else ssl.create_default_context()
        )

    def request(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str],
        body: bytes | None,
        timeout_seconds: float,
    ) -> KubernetesResponse:
        http_request = request.Request(url, data=body, headers=headers, method=method)
        try:
            with request.urlopen(
                http_request,
                timeout=timeout_seconds,
                context=self._context,
            ) as response:
                return KubernetesResponse(
                    status=response.status,
                    body=response.read(MAX_KUBERNETES_RESPONSE_BYTES),
                )
        except error.HTTPError as exc:
            return KubernetesResponse(
                status=exc.code,
                body=exc.read(MAX_KUBERNETES_RESPONSE_BYTES),
            )
        except OSError as exc:
            raise KubernetesExecutionError("Kubernetes API transport failed.") from exc


def _object_dict(value: object, *, label: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise KubernetesExecutionError(f"{label} is not a JSON object.")
    return cast(dict[str, object], value)


def _object_list(value: object) -> list[object]:
    if not isinstance(value, list):
        return []
    return cast(list[object], value)


def _positive_int(value: object) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) and value > 0 else 0


class KubernetesSandboxExecutor:
    def __init__(
        self,
        config: KubernetesApiConfig,
        *,
        transport: KubernetesTransport | None = None,
    ) -> None:
        self.config = config
        self.transport = transport or UrllibKubernetesTransport(config.ca_file)

    def _request(
        self,
        method: str,
        path: str,
        *,
        payload: Mapping[str, object] | None = None,
        expected: set[int] | None = None,
    ) -> KubernetesResponse:
        body = (
            json.dumps(dict(payload), separators=(",", ":"), ensure_ascii=False).encode("utf-8")
            if payload is not None
            else None
        )
        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {self.config.bearer_token}",
        }
        if body is not None:
            headers["Content-Type"] = "application/json"
        response = self.transport.request(
            method,
            f"{self.config.api_url}{path}",
            headers=headers,
            body=body,
            timeout_seconds=10.0,
        )
        allowed = expected or {200}
        if response.status not in allowed:
            detail = response.body.decode("utf-8", errors="replace")[:1500]
            raise KubernetesExecutionError(
                f"Kubernetes API {method} {path} returned {response.status}: {detail}"
            )
        return response

    @staticmethod
    def _json(response: KubernetesResponse) -> dict[str, object]:
        try:
            decoded: object = json.loads(response.body or b"{}")
        except json.JSONDecodeError as exc:
            raise KubernetesExecutionError("Kubernetes API returned malformed JSON.") from exc
        return _object_dict(decoded, label="Kubernetes API response")

    def _execution_handle(self, execution_id: UUID, policy: Mapping[str, object]) -> SandboxHandle:
        namespace = self.config.namespace
        job_name = sandbox_job_name(execution_id)
        policy_meta = _object_dict(policy.get("metadata"), label="NetworkPolicy metadata")
        policy_name_value = policy_meta.get("name")
        if not isinstance(policy_name_value, str) or not policy_name_value:
            raise KubernetesExecutionError("Execution NetworkPolicy name is invalid.")
        return SandboxHandle(
            execution_id=execution_id,
            namespace=namespace,
            job_name=job_name,
            input_secret_name=f"input-{job_name}",
            network_policy_name=policy_name_value,
        )

    def _create_resources(
        self,
        *,
        handle: SandboxHandle,
        secret: Mapping[str, object],
        policy: Mapping[str, object],
        job: Mapping[str, object],
    ) -> SandboxHandle:
        try:
            self._request(
                "POST",
                f"/api/v1/namespaces/{handle.namespace}/secrets",
                payload=secret,
                expected={201, 409},
            )
            self._request(
                "POST",
                f"/apis/networking.k8s.io/v1/namespaces/{handle.namespace}/networkpolicies",
                payload=policy,
                expected={201, 409},
            )
            self._request(
                "POST",
                f"/apis/batch/v1/namespaces/{handle.namespace}/jobs",
                payload=job,
                expected={201, 409},
            )
        except Exception:
            self.cleanup(handle)
            raise
        return handle

    def create_python_execution(
        self,
        *,
        execution_id: UUID,
        request_payload: dict[str, object],
        profile_name: str,
    ) -> SandboxHandle:
        namespace = self.config.namespace
        policy = cast(
            dict[str, object],
            build_network_policy(execution_id=execution_id, namespace=namespace),
        )
        handle = self._execution_handle(execution_id, policy)
        secret: dict[str, object] = {
            "apiVersion": "v1",
            "kind": "Secret",
            "metadata": {
                "name": handle.input_secret_name,
                "namespace": namespace,
                "labels": {"rigor.io/execution-id": str(execution_id)},
            },
            "type": "Opaque",
            "stringData": {
                "request.json": json.dumps(
                    request_payload,
                    separators=(",", ":"),
                    ensure_ascii=False,
                )
            },
        }
        job = cast(
            dict[str, object],
            build_python_job(
                execution_id=execution_id,
                namespace=namespace,
                input_secret_name=handle.input_secret_name,
                runner_image=self.config.runner_image,
                profile_name=profile_name,
            ),
        )
        return self._create_resources(handle=handle, secret=secret, policy=policy, job=job)

    def create_sql_execution(
        self,
        *,
        execution_id: UUID,
        request_payload: dict[str, object],
        profile_name: str,
    ) -> SandboxHandle:
        namespace = self.config.namespace
        policy = cast(
            dict[str, object],
            build_network_policy(execution_id=execution_id, namespace=namespace),
        )
        handle = self._execution_handle(execution_id, policy)
        secret: dict[str, object] = {
            "apiVersion": "v1",
            "kind": "Secret",
            "metadata": {
                "name": handle.input_secret_name,
                "namespace": namespace,
                "labels": {"rigor.io/execution-id": str(execution_id)},
            },
            "type": "Opaque",
            "stringData": {
                "request.json": json.dumps(
                    request_payload,
                    separators=(",", ":"),
                    ensure_ascii=False,
                ),
                "owner-password": secrets.token_urlsafe(32),
                "candidate-password": secrets.token_urlsafe(32),
            },
        }
        job = cast(
            dict[str, object],
            build_sql_job(
                execution_id=execution_id,
                namespace=namespace,
                input_secret_name=handle.input_secret_name,
                runner_image=self.config.sql_runner_image,
                postgres_image=self.config.sql_postgres_image,
                profile_name=profile_name,
            ),
        )
        return self._create_resources(handle=handle, secret=secret, policy=policy, job=job)

    def observe(self, handle: SandboxHandle) -> SandboxObservation:
        response = self._request(
            "GET",
            f"/apis/batch/v1/namespaces/{handle.namespace}/jobs/{handle.job_name}",
            expected={200, 404},
        )
        if response.status == 404:
            return SandboxObservation(state="MISSING", reason="job_not_found")

        job = self._json(response)
        status = _object_dict(job.get("status") or {}, label="Job status")
        for raw_condition in _object_list(status.get("conditions")):
            if not isinstance(raw_condition, dict):
                continue
            condition = cast(dict[str, object], raw_condition)
            if condition.get("status") != "True":
                continue
            condition_type = condition.get("type")
            if condition_type == "Complete":
                return SandboxObservation(state="SUCCEEDED", logs=self._runner_logs(handle))
            if condition_type == "Failed":
                reason = condition.get("reason")
                return SandboxObservation(
                    state="FAILED",
                    logs=self._runner_logs(handle),
                    reason=reason if isinstance(reason, str) else "job_failed",
                )
        if _positive_int(status.get("active")) > 0:
            return SandboxObservation(state="RUNNING")
        return SandboxObservation(state="PENDING")

    def _runner_logs(self, handle: SandboxHandle) -> str:
        selector = parse.quote(f"rigor.io/execution-id={handle.execution_id}", safe="")
        response = self._request(
            "GET",
            f"/api/v1/namespaces/{handle.namespace}/pods?labelSelector={selector}",
        )
        payload = self._json(response)
        items = _object_list(payload.get("items"))
        if not items:
            raise KubernetesExecutionError("Execution Job has no runner Pod.")
        pod = _object_dict(items[0], label="Execution Pod")
        metadata = _object_dict(pod.get("metadata"), label="Execution Pod metadata")
        pod_name_value = metadata.get("name")
        if not isinstance(pod_name_value, str) or not pod_name_value:
            raise KubernetesExecutionError("Execution Pod name is unavailable.")
        pod_name = parse.quote(pod_name_value, safe="")
        log_response = self._request(
            "GET",
            (
                f"/api/v1/namespaces/{handle.namespace}/pods/{pod_name}/log"
                "?container=runner&tailLines=2000"
            ),
        )
        return log_response.body.decode("utf-8", errors="replace")

    def cleanup(self, handle: SandboxHandle) -> None:
        resources: tuple[tuple[str, Mapping[str, object] | None], ...] = (
            (
                f"/apis/batch/v1/namespaces/{handle.namespace}/jobs/{handle.job_name}",
                {
                    "apiVersion": "v1",
                    "kind": "DeleteOptions",
                    "propagationPolicy": "Background",
                },
            ),
            (
                f"/apis/networking.k8s.io/v1/namespaces/{handle.namespace}/networkpolicies/"
                f"{handle.network_policy_name}",
                None,
            ),
            (
                f"/api/v1/namespaces/{handle.namespace}/secrets/{handle.input_secret_name}",
                None,
            ),
        )
        for path, payload in resources:
            try:
                self._request("DELETE", path, payload=payload, expected={200, 202, 404})
            except KubernetesExecutionError:
                # Cleanup is reconciled independently. Never replace a durable
                # terminal execution result with a cleanup transport failure.
                continue
