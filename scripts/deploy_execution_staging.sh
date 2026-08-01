#!/usr/bin/env bash
set -euo pipefail

required=(
  AWS_REGION
  RIGOR_STAGING_EKS_CLUSTER
  RIGOR_EXECUTION_QUEUE_URL
  RIGOR_STAGING_DATABASE_EXECUTOR_SECRET_ID
  RIGOR_EXECUTION_CONTROLLER_IMAGE
  RIGOR_PYTHON_RUNNER_IMAGE
  RIGOR_SQL_RUNNER_IMAGE
  RIGOR_SQL_POSTGRES_IMAGE
  RIGOR_STAGING_PROBE_IMAGE
)
for name in "${required[@]}"; do
  if [[ -z "${!name:-}" ]]; then
    echo "${name} is required" >&2
    exit 2
  fi
done

for image_var in \
  RIGOR_EXECUTION_CONTROLLER_IMAGE \
  RIGOR_PYTHON_RUNNER_IMAGE \
  RIGOR_SQL_RUNNER_IMAGE \
  RIGOR_SQL_POSTGRES_IMAGE \
  RIGOR_STAGING_PROBE_IMAGE; do
  image="${!image_var}"
  if [[ ! "${image}" =~ @sha256:[0-9a-f]{64}$ ]]; then
    echo "${image_var} must be pinned by sha256 digest" >&2
    exit 2
  fi
done

context="${RIGOR_STAGING_KUBE_CONTEXT:-rigor-staging-execution}"
namespace="${RIGOR_EXECUTION_NAMESPACE:-rigor-execution}"
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
controller_source="${repo_root}/infra/kubernetes/execution-controller.yaml"
boundary_source="${repo_root}/infra/kubernetes/execution-boundary.yaml"

tmpdir="$(mktemp -d)"
trap 'rm -rf "${tmpdir}"' EXIT
rendered_controller="${tmpdir}/execution-controller.yaml"

aws eks update-kubeconfig \
  --region "${AWS_REGION}" \
  --name "${RIGOR_STAGING_EKS_CLUSTER}" \
  --alias "${context}" >/dev/null

kubectl --context "${context}" apply -f "${boundary_source}"

cat <<'YAML' | kubectl --context "${context}" apply -f -
apiVersion: v1
kind: Namespace
metadata:
  name: rigor-system
  labels:
    app.kubernetes.io/part-of: rigor
    rigor.io/trust-plane: trusted-control
    pod-security.kubernetes.io/enforce: restricted
    pod-security.kubernetes.io/enforce-version: latest
    pod-security.kubernetes.io/audit: restricted
    pod-security.kubernetes.io/warn: restricted
YAML

executor_secret_json="$(aws secretsmanager get-secret-value \
  --region "${AWS_REGION}" \
  --secret-id "${RIGOR_STAGING_DATABASE_EXECUTOR_SECRET_ID}" \
  --query SecretString \
  --output text)"
executor_database_url="$(python3 -c '
import json, sys
value = json.load(sys.stdin)
url = value.get("database_url")
if not isinstance(url, str) or not url:
    raise SystemExit("executor secret has no database_url")
print(url)
' <<< "${executor_secret_json}")"
unset executor_secret_json

kubectl --context "${context}" -n rigor-system create configmap rigor-execution-controller \
  --from-literal="queue-url=${RIGOR_EXECUTION_QUEUE_URL}" \
  --from-literal="aws-region=${AWS_REGION}" \
  --from-literal="python-runner-image=${RIGOR_PYTHON_RUNNER_IMAGE}" \
  --from-literal="sql-runner-image=${RIGOR_SQL_RUNNER_IMAGE}" \
  --from-literal="sql-postgres-image=${RIGOR_SQL_POSTGRES_IMAGE}" \
  --dry-run=client -o yaml \
  | kubectl --context "${context}" apply -f -

kubectl --context "${context}" -n rigor-system create secret generic rigor-execution-controller \
  --from-literal="database-url=${executor_database_url}" \
  --dry-run=client -o yaml \
  | kubectl --context "${context}" apply -f -
unset executor_database_url

python3 - "${controller_source}" "${rendered_controller}" "${RIGOR_EXECUTION_CONTROLLER_IMAGE}" <<'PY'
from pathlib import Path
import sys

source = Path(sys.argv[1]).read_text(encoding="utf-8")
destination = Path(sys.argv[2])
image = sys.argv[3]
sentinel = (
    "rigor-execution-controller.invalid/replace-me@sha256:"
    "0000000000000000000000000000000000000000000000000000000000000000"
)
if source.count(sentinel) != 1:
    raise SystemExit("controller image sentinel must occur exactly once")
if "@sha256:" not in image:
    raise SystemExit("controller image must be digest pinned")
destination.write_text(source.replace(sentinel, image), encoding="utf-8")
PY

if grep -q 'replace-me' "${rendered_controller}"; then
  echo "controller manifest still contains replacement sentinel" >&2
  exit 3
fi

kubectl --context "${context}" apply -f "${rendered_controller}"
kubectl --context "${context}" -n rigor-system rollout status \
  deployment/execution-controller --timeout=180s

python3 - "${context}" <<'PY'
import json
import subprocess
import sys

context = sys.argv[1]
raw = subprocess.check_output(
    [
        "kubectl", "--context", context, "-n", "rigor-system", "get", "pods",
        "-l", "app.kubernetes.io/name=rigor-execution-controller", "-o", "json",
    ],
    text=True,
)
pods = json.loads(raw).get("items", [])
if len(pods) < 2:
    raise SystemExit("expected at least two execution-controller pods")
for pod in pods:
    node_name = pod.get("spec", {}).get("nodeName")
    if not node_name:
        raise SystemExit("execution-controller pod has no node")
    node_raw = subprocess.check_output(
        ["kubectl", "--context", context, "get", "node", node_name, "-o", "json"],
        text=True,
    )
    labels = json.loads(node_raw).get("metadata", {}).get("labels", {})
    if labels.get("workload") != "trusted-execution-control":
        raise SystemExit(f"controller pod scheduled on non-trusted node {node_name}")
PY

export RIGOR_STAGING_KUBE_CONTEXT="${context}"
export RIGOR_EXECUTION_NAMESPACE="${namespace}"
python3 "${repo_root}/scripts/validate_execution_staging.py"
python3 "${repo_root}/scripts/validate_execution_isolation.py"

echo "EXECUTION STAGING DEPLOYED AND LIVE ISOLATION VALIDATED."
