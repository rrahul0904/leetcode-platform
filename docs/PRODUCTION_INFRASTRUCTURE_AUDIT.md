# Rigor Production Infrastructure Audit

## Objective

Production must separate trusted SaaS workloads from hostile candidate execution.

## Trust planes

### Control plane

- Next.js web application
- FastAPI API
- trusted asynchronous workers
- OIDC and authorization
- RDS PostgreSQL/pgvector
- ElastiCache Valkey
- S3
- candidate profiles, questions, practice, submissions, evidence, and readiness

### Execution plane

- untrusted Python
- untrusted SQL
- temporary source and input
- temporary files
- ephemeral PostgreSQL databases
- bounded execution output

Candidate workloads are treated as compromised by design.

## Existing repository starting point

The repository already provides:

- production-oriented Docker images for the local application plane;
- local PostgreSQL/pgvector and Valkey;
- execution domain contracts and database records;
- a local functional Python adapter;
- a Kubernetes Job adapter contract;
- sandbox manifests/policies under the existing infrastructure boundary;
- server-controlled practice and submission behavior.

Production AWS infrastructure has not been verified or deployed by this branch.

## Target AWS architecture

- Route 53 for DNS.
- CloudFront and WAF for public edge protection and static delivery.
- ALB to route trusted dynamic traffic.
- ECS Fargate for Next.js, FastAPI, and trusted workers.
- RDS PostgreSQL with pgvector in private data subnets.
- ElastiCache Valkey in private data subnets.
- private encrypted S3 buckets.
- SQS for execution dispatch.
- a trusted execution orchestrator.
- a dedicated EKS/Kubernetes execution plane with containerd and gVisor.

## Non-negotiable isolation

Candidate execution must not have direct access to:

- application RDS;
- Valkey;
- internal ECS services;
- private FastAPI endpoints;
- Secrets Manager or SSM;
- AWS metadata endpoints;
- arbitrary AWS APIs;
- arbitrary internet egress;
- another candidate sandbox.

Candidate pods receive no application credentials and no service-account token.

## Queue and state requirements

Canonical states:

- `QUEUED`
- `DISPATCHING`
- `RUNNING`
- `COMPLETED`
- `FAILED`
- `TIMEOUT`
- `CANCELLED`
- `INFRASTRUCTURE_ERROR`

SQS is at-least-once delivery. Workers must atomically claim work and acknowledge already-finalized executions without running code again.

A durable outbox or an equivalent transactionally reliable publisher is required so a committed execution record cannot be silently separated from its queue message.

## SQL execution

Candidate SQL must never run on application RDS.

Each initial SQL execution uses an ephemeral PostgreSQL container/sidecar:

1. start PostgreSQL;
2. load trusted DDL and seed data;
3. create a restricted candidate role;
4. enforce statement, lock, and idle timeouts;
5. execute candidate SQL;
6. capture bounded and sanitized output;
7. destroy the Job.

Pre-warmed pools are deferred until measured demand justifies them.

## Terraform structure

The production implementation should use:

```text
infra/terraform/
  modules/
    networking/
    iam/
    kms/
    ecr/
    ecs/
    rds/
    valkey/
    storage/
    queues/
    execution/
    observability/
    waf/
    dns/
  environments/
    staging/
    production/
```

Staging and production must not share databases, OIDC clients, buckets, queues, execution clusters, or secrets.

## Verification policy

Infrastructure code is not equivalent to a verified deployment.

Completion reports must distinguish:

- implemented as code;
- verified locally;
- verified in staging AWS;
- verified in production AWS;
- not verified.

Critical sandbox acceptance tests must prove denial of RDS, Valkey, metadata, internet, cross-pod, privilege escalation, host mounting, unbounded runtime, disk exhaustion, and output flooding.

## Immediate implementation sequence

1. Terraform remote-state/bootstrap design.
2. VPC, subnet, route, endpoint, IAM, and KMS boundaries.
3. RDS, Valkey, S3, ECR, and SQS.
4. ECS web/API/trusted worker services.
5. CloudFront, WAF, ALB, Route 53, and TLS.
6. Transactional execution outbox and idempotent worker claims.
7. Dedicated execution cluster/node groups.
8. gVisor RuntimeClass and deny-all policies.
9. Python and ephemeral SQL runtimes.
10. observability, autoscaling, cost controls, CI/CD, and recovery tests.
