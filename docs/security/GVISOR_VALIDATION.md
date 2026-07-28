# gVisor Validation

Status: **NOT YET VALIDATED IN STAGING**

The repository contains a `RuntimeClass` contract using handler `runsc` and candidate Jobs set `runtimeClassName: gvisor`. That is source implementation, not proof that EKS nodes actually run gVisor.

Do not mark execution sandboxing production-ready until all evidence below is captured from the staging execution cluster.

## Required infrastructure evidence

```bash
kubectl get runtimeclass gvisor -o yaml
kubectl get nodes -l rigor.io/gvisor=true -o wide
kubectl describe node <execution-node>
```

The execution node pool must be isolated from SaaS workloads and must have the `runsc` runtime configured successfully.

## Required candidate Job evidence

Launch a staging execution through the same dispatcher path used by the product, then capture:

```bash
kubectl -n rigor-execution get job
kubectl -n rigor-execution get pod -l rigor.io/execution-id=<execution-id> -o yaml
kubectl -n rigor-execution describe pod <pod>
```

Verify at minimum:

- `runtimeClassName: gvisor`;
- the Pod is scheduled only to an execution node;
- `automountServiceAccountToken: false`;
- service account is `candidate-execution` and has no IRSA/EKS Pod Identity association;
- no AWS credential environment variables exist;
- default-deny network policy selects the Pod;
- root filesystem is read-only;
- `allowPrivilegeEscalation: false`;
- all Linux capabilities are dropped;
- CPU/memory/ephemeral-storage limits match the server-selected profile;
- Job deadline/backoff/TTL are present.

## Runtime proof

Node/runtime validation must prove the sandbox is handled by `runsc`, not merely that a Kubernetes `RuntimeClass` object exists. Capture the node runtime configuration and one successful staging Job execution showing that gVisor is active.

## Adversarial acceptance

Run the staging security suite against the real Job path. Candidate payloads must attempt:

```text
read container files
write outside /workspace
inspect environment
access IMDS
access AWS endpoints
access application RDS
access Valkey
access FastAPI/Web
access Kubernetes API
reach another candidate sandbox
reach public Internet
spawn subprocesses
consume CPU/memory
flood stdout/stderr
sleep beyond timeout
inspect procfs
```

Record command, execution ID, observed result, expected control, and any Kubernetes/CloudWatch evidence. Container-local information that is harmless may be readable, but host/credential/control-plane/tenant secrets must remain inaccessible and candidate-visible output must remain sanitized.

## Evidence table

| Check | Evidence | Status |
| --- | --- | --- |
| RuntimeClass exists | Not captured | Pending |
| Execution nodes use `runsc` | Not captured | Pending |
| Candidate Job scheduled on execution-only node | Not captured | Pending |
| AWS credentials absent | Unit manifest checks only | Pending staging proof |
| Kubernetes token absent | Source manifest only | Pending staging proof |
| Default-deny network effective | Source manifest only | Pending staging proof |
| Resource exhaustion contained | Not captured | Pending |
| Timeout terminates Job | Runner/source limits only | Pending staging proof |
| Sandbox cleanup verified | Not implemented end-to-end | Pending |

A completed table with staging evidence is required before this document may say `VALIDATED`.
