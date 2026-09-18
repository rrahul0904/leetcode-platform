# SkillForge AI Production Stack

This document records the target production architecture for SkillForge AI and the implementation boundaries enforced by the repository.

## Runtime topology

```text
Candidate Web / Vercel Next.js
        |
        | HTTPS + OIDC bearer identity
        v
FastAPI API / AWS ECS Fargate
        |
        +---- Aurora or RDS PostgreSQL   transactional source of truth
        +---- ElastiCache Valkey         cache, rate limits, idempotency
        +---- S3 private buckets         candidate files, imports, exports
        +---- SQS                        execution/background work
                    |
                    v
             isolated workers
             Python / SQL execution
```

Candidate code must never execute in Next.js or the FastAPI process. Execution is represented durably in PostgreSQL and dispatched to the isolated execution plane.

## Identity and authorization

Production identity is delegated to Clerk first, with Auth0-compatible OIDC validation retained as an enterprise path. SkillForge never stores user passwords.

The external provider establishes identity. PostgreSQL remains authoritative for SkillForge account status, roles, permissions, organization membership, candidate profile data, entitlements, and audit state. A provider-side custom claim is therefore not sufficient to grant a SkillForge role.

Clerk webhook processing is signature-verified and idempotent. External identity subjects are mapped to local `users` rows before authenticated application access is authorized.

## Persistence

PostgreSQL is the transactional system of record. The migration chain includes identity/onboarding, content/practice/progress, governed attachment question-bank metadata, and the SkillForge SaaS foundation in revision `20260826_0017`.

The SaaS foundation includes user preferences, identity webhook events, login events, candidate-file metadata, generated reports, data-export and deletion requests, plans, subscriptions, and entitlements. Sensitive candidate-owned tables use row-level security policies.

Large files are not stored as PostgreSQL blobs. `candidate_files` stores metadata and S3 storage keys. Upload and download access uses short-lived signed URLs against private S3 buckets.

## Local development

The repository local stack uses Docker Compose for PostgreSQL, Valkey/Redis, API services, workers, and execution-plane dependencies. The Next.js workspace can also run directly through pnpm.

Typical commands:

```bash
cp .env.example .env
docker compose up --build
```

For the JavaScript workspace:

```bash
pnpm install --frozen-lockfile
pnpm --filter @rigor/web dev
```

For the Python workspace:

```bash
uv sync --frozen --group dev
uv run alembic upgrade head
uv run uvicorn rigor_api.main:app --app-dir apps/api/src --reload
```

## Production infrastructure

Terraform under `infra/terraform` defines the AWS production foundation, including networking, ECS, load balancing, relational database, Valkey, SQS, S3, ECR, secrets, CloudWatch/logging integration, Route 53, ACM, CloudFront, and WAF components. Execution infrastructure remains isolated from normal SaaS workloads.

## Verification gates

A production change is not considered ready merely because code exists. Required evidence includes:

- frozen dependency installs;
- frontend lint, typecheck, tests, and production build;
- Ruff and Pyright;
- backend Pytest suite;
- PostgreSQL migration upgrade/downgrade cycle;
- Docker Compose validation and local release smoke checks;
- execution image builds and supply-chain/security checks;
- Terraform format and validate;
- worker smoke tests.

The separate 11,979-record question-bank release has its own exact database verification gate. A source artifact count is not equivalent to a verified live PostgreSQL load.

## Current implementation boundary

This architecture is intentionally incremental. PostgreSQL full-text search remains the first search engine; OpenSearch should only be introduced if measured search/recommendation requirements justify the additional operational surface. Redis/Valkey is never permanent candidate storage, and S3 objects remain private by default.
