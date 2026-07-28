# Sandbox Security

Status: source controls implemented; staging validation pending.

Candidate workloads are assumed malicious. Python restrictions inside the runner are defense in depth only; the security boundary is the isolated execution infrastructure plus gVisor and Kubernetes controls.

## Current source controls

| Control | Source evidence | Validation state |
| --- | --- | --- |
| gVisor RuntimeClass | `infra/kubernetes/execution-boundary.yaml` | Not proven on a node |
| Execution-only namespace | `rigor-execution` namespace | Not deployed |
| Restricted Pod Security | namespace enforce/audit/warn labels | Not deployed |
| No Kubernetes token | dedicated SA + `automountServiceAccountToken: false` | Manifest test only |
| No AWS credentials in Job env | sandbox Job builder | Manifest test only |
| Default-deny ingress/egress | namespace policy + per-execution policy builder | Not tested with CNI |
| No host namespaces | hostNetwork/PID/IPC false | Manifest test only |
| Non-root | UID/GID 65532 | Manifest test only |
| Read-only root filesystem | runner container security context | Manifest test only |
| No privilege escalation | container security context | Manifest test only |
| Drop capabilities | `ALL` | Manifest test only |
| Seccomp | RuntimeDefault | Manifest test only |
| CPU/memory/storage bounds | server-controlled profiles + quota/LimitRange | Not measured |
| Runtime deadline | execution/job deadlines | Not tested in cluster |
| Immutable runtime image requirement | sandbox image-reference validation | Unit test authored |
| Candidate source excluded from SQS | queue event contract | Unit test authored |
| Hidden expected answers excluded from sandbox | runner request validation | Unit test authored |
| Hidden stdout/stderr suppression | runner result projection | Unit test authored |

## Credential isolation

Candidate Jobs use the `candidate-execution` service account, which has token automount disabled and currently has no IRSA/EKS Pod Identity annotation in source. Production infrastructure must additionally ensure:

- no IAM role association is added to this service account;
- EC2 instance metadata is unreachable from candidate Pods;
- execution nodes do not expose host credentials into Pods;
- Secrets Manager and platform AWS APIs are blocked by network/IAM boundaries.

## Network isolation

The namespace is deny-all by default. Python execution requires no external egress.

SQL execution will eventually need one narrowly scoped path to its disposable PostgreSQL sidecar/Pod only. That exception must select the same execution identity and must not allow access to application RDS, Valkey, FastAPI, Kubernetes API, metadata endpoints, other sandboxes, or the public Internet.

## Hidden test protection

The candidate process necessarily receives the input of the test it is executing, so hidden-test secrecy cannot rely on hiding input from the process. Instead:

- expected answers remain trusted and never enter the sandbox;
- hidden stdout/stderr is not returned to the candidate;
- actual hidden outputs are returned only to trusted comparison logic;
- the public result sanitizer must expose only aggregate hidden pass/fail information.

The candidate runtime must never receive a file containing hidden expected outputs.

## Resource exhaustion

Defense is layered:

1. Kubernetes CPU/memory/ephemeral-storage limits.
2. namespace ResourceQuota/LimitRange.
3. Job active deadline and no Kubernetes retry.
4. Python child RLIMIT controls for CPU, file size, file descriptors and process count where supported.
5. bounded captured output.

These controls are not considered complete until fork/CPU/memory/disk/output/sleep attacks are executed against staging.

## Required adversarial staging suite

Candidate payloads must attempt:

- filesystem reads and writes outside the workspace;
- environment inspection;
- IMDS access;
- AWS endpoint/credential access;
- application RDS/Valkey/API access;
- Kubernetes API access;
- cross-sandbox access;
- Internet egress;
- subprocess/fork abuse;
- CPU and memory exhaustion;
- disk exhaustion;
- stdout/stderr flooding;
- infinite sleep;
- procfs inspection;
- import and runtime escape techniques.

Each case must record execution ID, expected control, observed behavior, candidate-visible output, Kubernetes outcome and any internal diagnostic evidence.

## Non-claims

The following statements are **not** yet supported:

- gVisor is running in staging;
- `runsc` is the effective runtime handler on execution nodes;
- default-deny networking is effective in the chosen EKS CNI configuration;
- IMDS/RDS/Valkey/Internet access has been proven blocked from a candidate Pod;
- resource-exhaustion attacks have been contained under production-equivalent load;
- sandbox cleanup is reliable after dispatcher/node failure.

See `docs/security/GVISOR_VALIDATION.md` before changing this status.
