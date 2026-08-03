# Local Docker Completion Audit

Verified against `main` at `11af54cb364872ea1aff0726dbca8864b23b1984`.

This document records executable repository behavior and the remaining work for a dependable local application. It does not claim production isolation, AWS deployment, or mobile completion.

## Current local topology

| Service | Purpose | Published port | Persistence | Current health/start behavior |
| --- | --- | ---: | --- | --- |
| `web` | Next.js candidate and administration application | `3001` | none | waits for healthy API; read-only filesystem |
| `api` | FastAPI application and local OIDC provider | `8002` | PostgreSQL | waits for migration, seed, content sync, local publication, and Valkey |
| `postgres` | Application PostgreSQL 18 with pgvector | `5434` | `rigor-postgres` | `pg_isready` health check |
| `valkey` | local cache/coordination service | `6381` | intentionally ephemeral | `valkey-cli ping` health check |
| `migrate` | Alembic upgrade to head | none | PostgreSQL | one-shot |
| `seed` | controlled taxonomy and local seed data | none | PostgreSQL | one-shot after migration |
| `catalog-init` | approved external-reference synchronization | none | PostgreSQL | one-shot after seed |
| `content-sync` | hosted package synchronization | none | PostgreSQL | one-shot after catalog initialization |
| `local-release` | controlled local publication cohort | none | PostgreSQL | one-shot before API startup |

The current Compose file does not start `execution-controller`, `python-runner`, `sql-runner`, OpenTelemetry, Prometheus, or Grafana.

## Existing startup contract

- `make bootstrap` delegates to `./scripts/start-populated-local`.
- The script validates Docker and Compose, builds the stack, waits for API/Web readiness, and verifies minimum external-reference, hosted-question, published-question, and synchronization counts.
- Expected browser URL: `http://localhost:3001`.
- Expected API URL: `http://localhost:8002`.
- `make reset-local` removes Compose volumes and rebuilds the populated stack.
- `make verify-local` checks Compose, API readiness, and the Web root.

## Existing security boundaries

- Candidate code is not executed in the Web container.
- Candidate code is not executed in the API container by the asynchronous production execution contract.
- Candidate SQL must never execute against application PostgreSQL.
- Production execution is designed for SQS, a trusted controller, Kubernetes Jobs, containerd, and gVisor.
- Local API configuration currently defaults to `LOCAL_FUNCTIONAL`; that adapter is explicitly forbidden in staging and production.
- Python and SQL runner images already exist and enforce bounded input, output, time, process/file limits, trusted-test separation, and non-root execution.
- Existing controller code is production-oriented and requires SQS plus Kubernetes.

## Current functional surfaces

The repository currently includes local OIDC, onboarding/profile, published problem catalog, Python/SQL practice workspace, asynchronous execution API contracts, progress/readiness, learning paths, mock exams, system-design content, company preparation, journal, resources, content ingestion, reviewer assignments, technical/editorial review, publication, and audit events.

## Known local completion gaps

### Execution

1. Compose does not start the existing controller or runner images.
2. The production controller requires AWS SQS and Kubernetes and therefore cannot service local queued executions.
3. A local controller transport is required that preserves the durable PostgreSQL execution aggregate and trusted result comparison while invoking dedicated runner services.
4. Python and SQL Run/Submit must be verified through the browser, including cancellation, idempotency, refresh recovery, and controller restart recovery.
5. Local execution must remain documented as a development boundary, not a substitute for gVisor.

### Operations and durability

1. `stop-local`, `logs-local`, `backup-local`, `restore-local`, and `release-local` targets are missing.
2. Backups do not yet include a manifest, Alembic revision, application revision, and checksum.
3. Restore verification and clean-volume recovery are not automated.
4. Dependency health does not yet expose runner/controller availability in a single operational endpoint.
5. Explicit application, execution, and observability networks are missing.

### Product completion

1. Primary navigation was recently upgraded, but every candidate and administration route still needs a dead-control and placeholder audit.
2. Browser E2E coverage is not yet the release gate for sign-in, onboarding, Python/SQL execution, bookmarks, notes, mock exams, reviewer publication, and sign-out.
3. Automated accessibility checks are not yet a release gate.
4. Local load budgets and execution-polling tests are not yet recorded.

### Observability

1. The API has OpenTelemetry dependencies and structured logging foundations, but Compose has no optional collector, Prometheus, or Grafana profile.
2. There is no local dashboard covering API errors, execution queue depth, execution latency/outcomes, runner availability, and database health.

### Documentation

1. `IMPLEMENTATION_PROGRESS.md` contains older counts and status statements that predate the merged execution, question-bank, recording-grade exam, curriculum, shell, journal, and resource work.
2. Local execution, environment variables, backup/restore, troubleshooting, and release-gate documentation must be made internally consistent.

## Phase implementation order

1. Harden Compose networks, health checks, resource limits, environment documentation, and Make targets.
2. Add a local controller and dedicated Python/SQL runner services while preserving the durable execution state machine.
3. Complete route/control audits and primary workflow E2E coverage.
4. Add backup/restore and restart-recovery tests.
5. Add accessibility, authorization, security, and local performance gates.
6. Add optional observability and a single `make release-local` gate.

## Acceptance rule

A phase is complete only when repository code, automated tests, and exact commands provide evidence. Missing infrastructure access or an unexecuted Docker workflow must be reported as unverified rather than inferred.