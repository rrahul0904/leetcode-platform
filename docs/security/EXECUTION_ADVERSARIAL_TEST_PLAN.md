# Execution Adversarial Staging Test Plan

Updated: 2026-07-30

## Status rule

This plan is not evidence that isolation works. `STAGING VALIDATED` requires execution of the live validators against the representative AWS/EKS environment and retention of their output.

The primary scripts are:

```bash
python scripts/validate_execution_staging.py
python scripts/validate_execution_isolation.py
```

Both fail closed. The staging probe image must be immutable and supplied as `RIGOR_STAGING_PROBE_IMAGE=<registry/image>@sha256:<digest>`.

The probe image must contain `/bin/sh`, `dmesg`, `env`, and `python3` for the validation commands.

## Runtime proof

`validate_execution_staging.py` verifies:

- `RuntimeClass/gvisor` exists and uses handler `runsc`;
- execution namespace is labeled as untrusted and enforces restricted Pod Security;
- candidate service-account token automount is disabled;
- namespace default NetworkPolicy denies ingress and egress;
- probe schedules on a node labeled `rigor.io/gvisor=true` and `workload=untrusted-execution`;
- the live sandbox's `dmesg` contains `Starting gVisor`.

A RuntimeClass YAML file alone is not acceptable runtime evidence.

## Credential and identity isolation

`validate_execution_isolation.py` fails if the candidate probe can observe common AWS credential-provider variables, including static/session credentials, web-identity configuration, role ARN, or ECS/EKS container credential endpoints.

It also fails when the Kubernetes service-account token is readable at the standard projected-token path.

For Python and SQL production images, additionally inspect the effective environment and mounted files from a real candidate Job. Secrets required by the trusted controller must never be projected into the candidate container.

## Network isolation

The live probe attempts connections to:

- AWS IMDS `169.254.169.254:80`;
- public Internet `1.1.1.1:443`;
- `kubernetes.default.svc:443`;
- public DNS resolution for `example.com`;
- optional internal staging targets from `RIGOR_STAGING_BLOCKED_TARGETS`.

Set the optional targets to include the actual staging FastAPI private endpoint, application RDS endpoint, Valkey endpoint, and any other sensitive control-plane service:

```bash
export RIGOR_STAGING_BLOCKED_TARGETS='api.internal:8000,staging-rds.example:5432,valkey.internal:6379'
```

Every connection must fail from the candidate sandbox.

## Filesystem isolation

The validator proves the candidate root filesystem is read-only. A real candidate Job should also be inspected to confirm only intended ephemeral mounts exist and no host paths, container-runtime sockets, controller tokens, or application configuration are mounted.

## Python abuse cases

Execute controlled Python cases for:

- infinite loop / wall-clock timeout;
- CPU saturation;
- memory growth beyond profile limit;
- process/fork attempt;
- many file descriptors;
- oversized file writes;
- oversized stdout/stderr;
- `/etc`, `/root`, `/proc`, and `/sys` access attempts;
- IMDS/Internet/internal-service socket attempts;
- AWS SDK default credential discovery;
- Kubernetes token/API discovery.

Expected result is a bounded candidate-safe FAILED/TIMEOUT outcome or ordinary denied operation. The controller must remain healthy and the Job/Secret/NetworkPolicy must be cleaned up.

## SQL abuse cases

Execute controlled PostgreSQL candidate statements for:

- `pg_sleep` beyond statement timeout;
- expensive cross joins / resource exhaustion;
- lock contention;
- `CREATE ROLE` / `ALTER ROLE`;
- `CREATE DATABASE`;
- extension creation;
- `COPY ... PROGRAM`;
- `pg_read_file` and related server-file functions;
- attempts to connect to the application RDS database;
- multi-command submissions.

The candidate account must remain non-superuser, non-role/database-creator, non-replicating, and isolated to the disposable execution database.

## Reliability injection

Run controlled failure injection for:

- duplicate queue delivery;
- controller termination after claim;
- controller termination after Job creation;
- controller termination after runner completion before result persistence;
- SQS visibility expiry;
- lease expiry with live Job;
- lease expiry with missing Job;
- Pod eviction / node loss;
- transient Kubernetes API failure;
- transient PostgreSQL failure;
- malformed/wrong-attempt runner result;
- cancellation racing completion.

Verify each execution converges to exactly one durable terminal state and no terminal execution is restarted.

## Evidence to retain

For a staging sign-off retain:

- CI run SHA used for deployment;
- image digests for controller, Python runner, SQL runner, PostgreSQL, and probe;
- `kubectl get runtimeclass gvisor -o yaml`;
- probe Pod YAML/status and node labels;
- gVisor `dmesg` proof;
- validator stdout/stderr;
- sanitized execution IDs/attempt transitions for failure injections;
- queue/DLQ observations;
- cleanup evidence showing no orphan Jobs/Secrets/NetworkPolicies.

Only after these pass should the execution boundary be labeled `STAGING VALIDATED`.
