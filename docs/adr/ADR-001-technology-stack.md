# ADR-001: Mandatory Technology Stack

- **Status:** Accepted
- **Date:** 2026-07-20

## Decision

Use Node.js 24 LTS, Next.js App Router, TypeScript strict mode, Python 3.13, FastAPI, Pydantic 2, SQLAlchemy 2, PostgreSQL 18 with pgvector, Valkey, Temporal, AWS, Terraform, OpenTelemetry, containerd, and gVisor. Begin with a modular monolith and explicit execution/worker boundaries.

## Rationale

This stack meets relational content integrity, typed API generation, durable workflows, interactive editing, hybrid search, cloud isolation, and auditability without premature microservices or redundant infrastructure.

## Alternatives considered

- GraphQL: rejected for MVP because REST/OpenAPI is sufficient and canonical type generation is required.
- Dedicated search/vector products: rejected at the initial catalog size; PostgreSQL supports lexical, trigram, metadata, and vector retrieval.
- Docker as production sandbox: rejected as an insufficient boundary for arbitrary code.

## Consequences

The team operates both ECS and an isolated EKS sandbox boundary. PostgreSQL requires deliberate schema and migration work. Temporal becomes operationally critical. AWS-specific identity and infrastructure increase cloud coupling but remain behind application interfaces where practical.

## Security and rollback

No candidate code crosses into the application plane. Each deploy retains a previous signed image; database migrations require explicit downgrade or forward-fix instructions. A stack substitution requires a new ADR, compatibility/security analysis, explicit approval, and rollback plan.

