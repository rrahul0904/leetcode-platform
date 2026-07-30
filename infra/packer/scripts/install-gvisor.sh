#!/usr/bin/env bash
set -euo pipefail

: "${GVISOR_ARCHIVE_URL:?GVISOR_ARCHIVE_URL is required}"
: "${GVISOR_SHA256:?GVISOR_SHA256 is required}"

if [[ ! "${GVISOR_ARCHIVE_URL}" =~ ^https:// ]]; then
  echo "gVisor archive URL must use HTTPS" >&2
  exit 2
fi
if [[ ! "${GVISOR_SHA256}" =~ ^[0-9a-f]{64}$ ]]; then
  echo "gVisor archive SHA-256 must be lowercase hexadecimal" >&2
  exit 2
fi

workdir="$(mktemp -d)"
trap 'rm -rf "${workdir}"' EXIT
archive="${workdir}/gvisor.tar.bz2"
extract_dir="${workdir}/gvisor"
mkdir -p "${extract_dir}"

if ! command -v bzip2 >/dev/null 2>&1; then
  sudo dnf install -y bzip2
fi

curl --fail --location --proto '=https' --tlsv1.2 \
  --retry 4 --retry-delay 2 \
  --output "${archive}" \
  "${GVISOR_ARCHIVE_URL}"

printf '%s  %s\n' "${GVISOR_SHA256}" "${archive}" | sha256sum --check --strict -
tar -xjf "${archive}" -C "${extract_dir}"

runsc_path="$(find "${extract_dir}" -type f -name runsc -print -quit)"
shim_path="$(find "${extract_dir}" -type f -name containerd-shim-runsc-v1 -print -quit)"
gvisor_bin_dir="$(find "${extract_dir}" -type d -name gvisor-bin -print -quit)"

if [[ -z "${runsc_path}" || -z "${shim_path}" || -z "${gvisor_bin_dir}" ]]; then
  echo "gVisor archive is missing runsc, containerd-shim-runsc-v1, or gvisor-bin" >&2
  exit 3
fi

sudo install -m 0755 "${runsc_path}" /usr/local/bin/runsc
sudo install -m 0755 "${shim_path}" /usr/local/bin/containerd-shim-runsc-v1
sudo rm -rf /usr/local/bin/gvisor-bin
sudo install -d -m 0755 /usr/local/bin/gvisor-bin
sudo cp -a "${gvisor_bin_dir}/." /usr/local/bin/gvisor-bin/
sudo find /usr/local/bin/gvisor-bin -type f -exec chmod 0755 {} +

# EKS AL2023 runs nodeadm automatically. A NodeConfig drop-in is merged after
# cluster/user-data configuration, so it adds the runsc runtime without editing
# the EKS-generated /etc/containerd/config.toml directly.
sudo install -d -m 0755 /etc/eks/nodeadm.d
cat <<'EOF' | sudo tee /etc/eks/nodeadm.d/20-runsc.yaml >/dev/null
---
apiVersion: node.eks.aws/v1alpha1
kind: NodeConfig
spec:
  containerd:
    config: |
      [plugins."io.containerd.grpc.v1.cri".containerd.runtimes.runsc]
        runtime_type = "io.containerd.runsc.v1"
EOF
sudo chmod 0644 /etc/eks/nodeadm.d/20-runsc.yaml

sudo /usr/local/bin/runsc --version
sudo test -x /usr/local/bin/containerd-shim-runsc-v1
sudo test -d /usr/local/bin/gvisor-bin
sudo grep -F 'runtime_type = "io.containerd.runsc.v1"' /etc/eks/nodeadm.d/20-runsc.yaml
