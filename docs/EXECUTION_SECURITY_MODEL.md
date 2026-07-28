# Rigor execution security model

## Trust boundary

Rigor has two security planes.

### Trusted control plane

FastAPI, Next.js, trusted background workers, PostgreSQL, Valkey, S3, OIDC integration, content/publication, submissions metadata, evidence, readiness, entitlements, and administrative systems.

### Hostile execution plane

Candidate Python, candidate SQL, temporary source/input files, ephemeral databases, and sandbox output.

A sandbox is assumed compromised while it exists.

## Prohibited paths

Candidate workloads must not have direct access to:

- application RDS;
- Valkey;
- FastAPI/Next.js private services;
- Secrets Manager or SSM;
- AWS credentials or ServiceAccount tokens;
- EC2 instance metadata;
- other candidate jobs;
- unrestricted internet egress.

## Defense layers

1. Execution jobs live in a dedicated EKS cluster, not the ECS application trust context.
2. Execution subnets have no default route to a NAT gateway or internet gateway.
3. gVisor workers are isolated by labels/taints and require a custom AMI proven to contain `runsc`.
4. Candidate pods select the gVisor RuntimeClass.
5. Namespace Pod Security Admission enforces the restricted profile.
6. Candidate pods use no ServiceAccount token, run non-root, drop capabilities, deny privilege escalation, use seccomp, and use a read-only root filesystem.
7. Kubernetes NetworkPolicy defaults ingress and egress to deny.
8. CPU, memory, ephemeral storage, job count, and pod count are bounded.
9. Execution nodes require IMDSv2 with hop limit 1; candidate pods receive no IAM identity.
10. Trusted dispatcher IAM is separate from execution-node IAM and sandbox containers receive neither role.

## Python

The current local functional runner is local-development functionality and is not a security boundary. Production Python must run only as a gVisor Kubernetes Job with bounded source/input/output/time/process/file resources.

## SQL

Candidate SQL must never use application RDS. Production SQL jobs create a disposable PostgreSQL instance/sidecar, apply trusted challenge DDL and seed data, create a restricted candidate role, execute/evaluate, sanitize output, and destroy the job.

## Queue semantics

SQS is at-least-once. Production workers must use atomic execution claims/leases and treat terminal executions as immutable so a redelivered message cannot execute a finalized attempt twice.

Queue messages should contain `execution_id`; candidate source and hidden test material remain in trusted storage.

## Required security acceptance tests

Before enabling production compute, prove a candidate job cannot reach RDS, Valkey, private FastAPI/ECS services, AWS metadata, Secrets Manager, arbitrary S3, internet, another sandbox, or host filesystems. Also prove timeout, memory/process/output/disk limits and duplicate-message idempotency.
