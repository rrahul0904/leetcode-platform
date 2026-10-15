# ADR-002: V1 Candidate Execution Provider

- Status: Accepted for V1; provider certification pending
- Date: 2026-10-13

## Decision

Vercel Sandbox is the only enabled V1 hosted execution provider. Hosted `KUBERNETES_JOB` requests fail with 503 and readiness reports `not_ready`. The EKS Terraform opt-in remains rejected until the controller uses authoritative API execution state through a proven network path.

## Context

The API persists requests in its application database. The optional Kubernetes controller consumes a separate execution database in another VPC. Queue existence does not prove a worker can claim the API's requests. The canonical product target is Vercel.

## Consequences

No hosted request may be durably accepted by the uncertified Kubernetes path. Vercel Sandbox still requires project-scoped credentials, bounded runtime/output/resources, durable result recovery and adversarial testing. Do not place database, Clerk, or provider credentials inside the sandbox.

## Revisit when

An ADR revision demonstrates shared authoritative execution state, least-privilege network access, migration and failure semantics, an applied topology, and passing isolation/recovery tests.
