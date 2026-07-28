# Multi-client and production infrastructure implementation notes

Status: implementation branch; not production approved.

## What this branch adds

- Expo/React Native candidate client for iOS, iPadOS, Android phones, and Android tablets.
- Platform-neutral API transport, query keys, and design tokens.
- Native Authorization Code + PKCE flow with SecureStore token persistence.
- Candidate home, published question catalog, responsive Python practice workspace, readiness/progress, onboarding, and profile screens.
- SQLite local-first practice drafts with server autosave and explicit conflict ordering.
- EAS development/preview/production build profiles without committing signing credentials.
- AWS Terraform modules for isolated networking, KMS, ECR, RDS PostgreSQL, Valkey, S3, SQS/DLQ, ECS Fargate, WAF, observability, IAM, and a private EKS execution plane.
- Kubernetes restricted namespace, gVisor RuntimeClass binding, deny-all network policy, LimitRange, and ResourceQuota.
- Separate staging and production Terraform roots and remote-state examples.

## Security boundary

The control plane is trusted application infrastructure. Candidate code is a hostile tenant workload.

Candidate code must never execute in Next.js, FastAPI, trusted ECS workers, the application RDS instance, browser/mobile clients, or CI.

The execution EKS node group is intentionally gated. Terraform creates no execution workers unless both a validated custom AMI and bootstrap payload are supplied. The AMI must prove containerd + runsc integration before `gvisor_node_group_created` can become true.

Execution subnets have no default internet/NAT route. Candidate pods are separately default-denied by Kubernetes NetworkPolicy and receive no ServiceAccount token.

## Deliberate production gate

`enable_control_plane_compute` defaults to `false` in both staging and production.

The current candidate submission implementation still calls the local functional execution adapter inline from the FastAPI request path. That adapter is useful for local development but is explicitly not a production security sandbox.

Therefore this branch does **not** deploy the ECS control plane by default. Enabling it before the SQS/outbox/dispatcher state machine replaces inline execution would violate the production trust model.

Required next execution milestone:

1. extend the execution state machine to `QUEUED -> DISPATCHING -> RUNNING -> terminal`;
2. persist an outbox row in the same transaction as the execution request;
3. publish only `execution_id` to SQS;
4. implement an idempotent trusted dispatcher with atomic claim/lease semantics;
5. launch gVisor Kubernetes Jobs from the dispatcher;
6. persist sanitized results and terminal state;
7. reconcile orphaned/expired jobs;
8. make Run/Submit APIs asynchronous and provide status/read APIs;
9. prove duplicate SQS delivery cannot execute a finalized submission twice;
10. only then enable ECS compute in staging.

## Database credentials

Terraform creates separate Secrets Manager records for `rigor_app` and `rigor_migrator`; it does not hand the RDS master credential to normal ECS tasks. A bootstrap deployment step still needs to create/update those PostgreSQL roles using the RDS-managed master secret, then run Alembic as `rigor_migrator`.

FastAPI can now receive database and Valkey credentials as individual secret-backed environment fields and compose TLS connection URLs at runtime, avoiding password-bearing DSNs in committed Terraform source.

## Web build routing

The web Dockerfile accepts `NEXT_PUBLIC_RIGOR_API_URL` as a build argument. Local builds keep `http://localhost:8002`; a production build can pass an empty value so browser requests use same-origin `/api/...` routes behind the ALB/edge layer.

## Honest gaps

The branch is not yet production complete. In particular:

- the durable interview-session backend does not exist, so the native Interviews tab does not invent separate state;
- SQS dispatch/outbox/worker code is not yet implemented;
- production PostgreSQL role bootstrap/migration job is not yet implemented;
- gVisor AMI build/validation automation is not yet implemented;
- DNS/CloudFront deployment is not yet implemented;
- execution worker autoscaling from queue depth/age is not yet implemented;
- OpenTelemetry exporter wiring, client crash SDK selection, restore automation, and store signing/submission remain later release work;
- staging/prod Terraform has not been applied and must not be described as AWS-verified.

## Verification policy

The draft PR workflow refreshes the lockfile and Terraform formatting on the same-repository branch, then runs the existing JavaScript and Python quality gates plus Terraform validation and production Docker builds.

Passing repository CI means implementation is verified in source/local build terms. It does not mean infrastructure has been verified in AWS, gVisor has been proven on a node, backups have been restored, or native binaries have been accepted by app stores.
