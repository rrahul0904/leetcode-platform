# Rigor Platform Implementation Audit

Audit date: 2026-07-28

This document supersedes older local-worktree observations with evidence from the current GitHub branch `feature/rigor-multiclient-infrastructure`. It deliberately distinguishes implementation, tests, integration validation, deployment, and production readiness.

## Branch evidence

At the start of this execution-plane slice, GitHub reported:

- feature branch ahead of `main`: **11 commits**;
- feature branch behind `main`: **0 commits**.

The previously stated estimate of roughly 134 commits ahead is not supported by the current GitHub branch and is not used as evidence here.

## Capability audit

| Capability | Source implemented? | Unit tested? | Integration tested? | Staging deployed? | Production-ready? | Evidence | Known gaps |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Next.js web application | Yes | Yes, existing suite | Local evidence only | No evidence | No | `apps/web`; existing progress ledger reports lint/typecheck/component/build validation | Async production execution client not yet proven in staging |
| FastAPI application | Yes | Yes, existing suite | Local evidence only | No evidence | No | `apps/api`; authenticated practice/submission routes | Current Run/Submit path still invokes local candidate execution synchronously |
| PostgreSQL persistence and migrations | Yes | Partial | Local migration evidence | No evidence | No | Alembic through `20260728_0008` before this slice; role/RLS foundation | New execution migration `20260728_0009` requires CI/database/staging validation |
| Valkey integration | Partial | Limited | Reachability check exists | No evidence | No | API readiness probe | No production ElastiCache deployment/failure validation |
| OIDC / authorization | Yes | Existing tests | Local | No evidence | No | normalized principal, permission checks, local OIDC/PKCE support | Production provider, redirects, token lifecycle and physical-device validation incomplete |
| Candidate profile | Yes | Existing tests | Local | No evidence | No | API/UI persistence and RLS context | No staging verification |
| Published question catalog | Yes | Existing tests | Local | No evidence | No | published-version filtering and candidate-safe response boundary | Production release validation remains separate |
| Practice sessions / server draft persistence | Yes | Existing tests | Local | No evidence | No | `practice.py`, PostgreSQL-backed sessions | Native local-first/offline claims are not evidenced by the inspected branch |
| Candidate Run API | Yes, legacy synchronous path | Existing local runner coverage | Local only | No | **No** | `/api/v1/questions/{slug}/run`; `LocalFunctionalPythonRunner` | FastAPI still executes candidate Python; must be rewired to durable async execution |
| Candidate Submit API | Yes, legacy synchronous path | Existing evaluation tests | Local only | No | **No** | submissions/evaluation/evidence persistence | Same production-isolation blocker; response contract is terminal/synchronous |
| Execution state-machine foundation | **Yes, this slice** | **Yes, this slice** | Not yet | No | No | `rigor_api/execution_domain.py`; `test_execution_domain.py` | Dispatcher/database integration not yet validated |
| Durable execution idempotency foundation | **Yes, this slice** | Request fingerprint unit-tested | Not yet | No | No | candidate-scoped uniqueness plus `request_hash` | Run/Submit endpoints still need endpoint-scoped key wiring |
| Transactional execution outbox | **Yes, this slice** | Retry policy unit-tested | Not yet | No | No | execution + payload + initial event + outbox can share one transaction; publisher claim uses `FOR UPDATE SKIP LOCKED` | SQS publisher service and trusted worker DB identity absent |
| Versioned queue event contract | **Yes, this slice** | **Yes** | Not yet | No | No | `execution.requested` schema v1 contains execution ID/attempt/time/trace only | No SQS send/receive verification |
| Execution leases | Schema/domain foundation | Transition tests | No | No | No | `lease_owner`, `lease_expires_at`, dispatch/running timestamps | Atomic dispatcher claim, renewal and reconciliation remain |
| Trusted execution dispatcher | No | No | No | No | No | Target architecture only | P0 implementation blocker |
| SQS + DLQ | No deployed implementation | No | No | No | No | Required in architecture docs/specification | Terraform, publisher, consumer, retry and DLQ operations absent |
| EKS execution cluster | No verified implementation | No | No | No | No | Target architecture only | Cluster/node groups/runtime not deployed |
| gVisor sandbox execution | Contract/design only | Local adapter tests are not gVisor tests | No | No | No | security intent and Kubernetes boundary documented | `runsc`/RuntimeClass proof and adversarial staging suite absent |
| Python production runner | No | Local functional runner tested | No | No | No | local runner explicitly states it is not a production security sandbox | Versioned runner image + EKS integration required |
| Disposable PostgreSQL candidate SQL | Partial local concepts | Limited | No production integration | No | No | local/trusted SQL execution foundations | Candidate SQL must use disposable isolated PostgreSQL, never application RDS |
| Execution cancellation | Domain foundation this slice | State-machine tests | No | No | No | durable cancel transition plus cancellation outbox event | API endpoint and Kubernetes deletion/convergence not wired |
| Reconciliation loop | No | No | No | No | No | Required by production design | P0 reliability gap |
| Execution artifacts | DB payload separation foundation | No integration test | No | No | No | source is outside queue in `execution_payloads`; reference fields exist | Production S3 execution-artifact flow and scoped access absent |
| Execution telemetry / metrics | Partial platform telemetry | Limited | No execution-plane validation | No | No | correlation/trace fields exist | Required metrics, dashboards and alerts incomplete |
| AWS SaaS infrastructure | Architecture/audit only on inspected branch | No deployment proof | No | No | No | `docs/PRODUCTION_INFRASTRUCTURE_AUDIT.md` states AWS is unverified/not deployed | Terraform implementation and staging deployment remain major work |
| CloudFront/WAF/ALB/Route53 | No verified deployment | No | No | No | No | Target architecture documented | TLS/routing/cache/origin validation absent |
| PostgreSQL role separation | Partial | Local bootstrap evidence | Local only | No | No | `rigor_migrator`, `rigor_app`, readonly and SQL sandbox roles defined locally | Secrets Manager/bootstrap/deployment verification required |
| One-shot migration deployment | No verified production workflow | No | No | No | No | Desired workflow documented | ECS migration task/deployment gate absent |
| Expo / React Native application | **Not evidenced by inspected feature branch** | Not evidenced | Not evidenced | No | No | `docs/MULTIPLATFORM_AUDIT.md` lists Expo scaffold/native flow/screens as not yet claimed complete | Re-audit additional unpublished/local work before making mobile completion claims |
| iOS / iPadOS physical E2E | No evidence | No | No | No | No | Device evidence document absent | Login/editor/Run/Submit/background/network/device validation required |
| Android phone/tablet physical E2E | No evidence | No | No | No | No | Device evidence document absent | Same physical-device validation gap |
| CI/CD | Existing validation foundation | Yes for existing areas | Partial | No deployment proof | No | repository documents lint/typecheck/test/build commands | New migration/domain tests must pass CI; immutable deploy/security stages remain |
| Supply-chain security | Partial / no full verified pipeline | Unknown | No production validation | No | No | production audit calls for scanning/SBOM/signing | Trivy/Syft/Cosign and signed-image deployment proof needed |
| Backup/PITR recovery | No deployment evidence | No | No | No | No | Required by production specification | Staging restore exercise/RTO/RPO evidence absent |
| Load/concurrency/failure injection | No production evidence | No | No | No | No | Required benchmark documents absent | 10/50/100/500 execution tests and crash/failure scenarios remain |

## Execution-plane changes introduced in this slice

1. Canonical production lifecycle: `QUEUED → DISPATCHING → RUNNING → COMPLETED`, with `FAILED`, `TIMEOUT` and `CANCELLED` terminal paths.
2. Explicit legal transition validation rejects terminal-state resurrection and skipped lifecycle transitions.
3. Candidate execution creation can persist the execution aggregate, source payload, initial event and outbox event inside one PostgreSQL transaction.
4. Queue events are versioned and contain no candidate source code.
5. Durable request fingerprints prevent silent reuse of one idempotency key for different code/requests.
6. Outbox workers can safely claim concurrent batches with `FOR UPDATE SKIP LOCKED` and retry with capped exponential backoff plus jitter.
7. Lease, dispatch, Kubernetes identity, resource-accounting and result-reference columns are introduced for dispatcher/reconciliation work.

## Immediate blockers

### P0

- Rewire Run/Submit away from `LocalFunctionalPythonRunner` to the durable async execution request path.
- Implement SQS publisher and consumer with a dedicated trusted worker database identity/policy.
- Implement atomic dispatcher claim, lease renewal and reconciliation.
- Implement/deploy the EKS + gVisor sandbox and versioned Python runner.
- Implement disposable PostgreSQL for candidate SQL.
- Deploy a representative staging environment and prove isolation.

### P1

- Async Web/native polling, cancellation and lifecycle recovery.
- DLQ operational recovery.
- Security/adversarial and failure-injection suites.
- Metrics, dashboards and alerts.
- One-shot migration deployment and database role/secrets bootstrap.

### P2

- Load/cost benchmarking and optimization after correctness/safety proof.
- Mock Interview durable domain only after the shared execution plane is healthy.

No capability is marked production-ready merely because source code exists.
