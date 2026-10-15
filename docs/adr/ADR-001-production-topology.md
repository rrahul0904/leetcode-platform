# ADR-001: Canonical V1 Production Topology

- Status: Accepted for V1; production certification pending
- Date: 2026-10-13

## Decision

Use one Vercel-first topology: browser → Next.js App Router on Vercel → same-origin `/api/backend` → FastAPI modular monolith → Clerk verification → Neon/PostgreSQL authoritative state → Vercel Sandbox for hostile candidate execution.

## Context

Repository configuration contains both Vercel services and an AWS ECS/EKS Terraform deployment. PR #51's EKS path has an independent execution database in a distinct VPC, while `skillforge-platform` is the active canonical Vercel project. A user-authorized project-scoped Preview automation bypass now permits application probes while platform protection remains enabled. The exact candidate's web routes returned 200, but API health returned 500 because the deployed Python runtime could not import FastAPI. Source configuration and deployment status alone are not certification.

## Consequences

Vercel is the only V1 release path. AWS/ECS/EKS remains deferred; it cannot be promoted by merely applying existing Terraform. Same-origin API calls remain behind the Next.js BFF. Application PostgreSQL is the sole authoritative candidate/execution state. Readiness and release receipts must prove the exact deployed runtime.

## Verification

Architecture checks and hosted probes are required. Current Preview API health, auth, DB and sandbox behavior remain unverified; the API import failure must be fixed before proceeding.
