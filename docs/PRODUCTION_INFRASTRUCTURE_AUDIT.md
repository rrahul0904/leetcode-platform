# Rigor production infrastructure audit

Baseline: repository state before `feature/multiclient-production-foundation`.

## Existing foundation

The repository already had hardened local Docker images, PostgreSQL/pgvector, Valkey, Alembic roles/migrations, candidate RLS, candidate-safe publication boundaries, execution interfaces, a local functional Python runner, a disposable PostgreSQL SQL runner, and a Kubernetes Job specification that encoded gVisor and restrictive pod-security expectations.

## Baseline production gaps

Before this branch there was no standing AWS production implementation for:

- VPC/subnet trust zones;
- ECS Fargate web/API/trusted workers;
- managed RDS PostgreSQL;
- managed Valkey;
- encrypted S3 artifacts;
- SQS execution dispatch/DLQ;
- ECR release registries;
- private EKS execution plane;
- validated gVisor worker nodes;
- WAF;
- production IAM boundaries;
- CloudWatch execution/data alarms;
- isolated staging/production Terraform roots.

## Existing execution risk

The candidate submission endpoint creates durable execution records but calls the local execution adapter inline before returning. That is appropriate for local functional development only. It cannot be deployed as the production FastAPI execution path because candidate source would then execute inside the trusted API container.

## Infrastructure implemented in this branch

### Network

- multi-AZ VPC;
- public ingress subnets;
- private trusted application subnets;
- isolated private data subnets;
- isolated execution subnets with no default NAT/internet route;
- private ECR/Logs/STS interface endpoints for trusted application networking;
- S3 gateway endpoint;
- separate web/API/trusted-worker security identities.

### Data/control services

- KMS separation between canonical platform data and transient execution data;
- RDS PostgreSQL with encryption, TLS enforcement, backups/PITR configuration, monitoring, private networking, and optional Multi-AZ;
- separate Secrets Manager records for application and migrator PostgreSQL roles;
- Valkey with TLS, at-rest encryption, authentication, private networking, and failover configuration;
- separate private/versioned/lifecycle-managed platform and execution S3 buckets;
- immutable encrypted ECR repositories;
- encrypted SQS execution queue and DLQ.

### Compute

- independent Fargate definitions/services for Next.js, FastAPI, and a future trusted dispatcher;
- ALB routing and deployment circuit breakers;
- private EKS execution cluster;
- execution-specific node role/security group;
- gVisor node group gated on a validated custom AMI + bootstrap;
- namespace-scoped EKS access for the trusted dispatcher role;
- RuntimeClass, restricted Pod Security Admission namespace, default-deny network policy, LimitRange, and ResourceQuota.

### Edge/operations

- regional WAF managed rules plus API/execution rate controls;
- queue/DLQ, RDS, and Valkey CloudWatch alarms;
- separate staging/production roots and state examples.

## Deliberately not represented as complete

- asynchronous SQS/outbox execution dispatcher;
- production DB role bootstrap and migration task;
- gVisor AMI build pipeline and runsc verification;
- queue-driven execution-node autoscaling;
- CloudFront/Route53 domain provisioning;
- restore test automation;
- OpenTelemetry exporter/backend configuration;
- native store signing and submission.

The Terraform stack keeps ECS control-plane compute disabled by default until the first item is complete.
