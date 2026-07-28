# Rigor Platform Implementation Audit

Audit date: 2026-07-28

This audit is based on the current GitHub branch `feature/rigor-multiclient-infrastructure`. It distinguishes source implementation, tests present in source, tests actually executed, staging deployment, and production readiness. A Terraform module, Kubernetes manifest, test file, or Dockerfile is not deployment proof.

## Branch evidence

At the start of this execution-plane slice GitHub reported **11 commits ahead of `main` and 0 behind**. After the implementation work recorded below, the branch is **50 commits ahead of `main` and 0 behind**.

The previously stated estimate of roughly 134 commits ahead is not supported by the current GitHub branch and is not used as evidence.

## Capability audit

| Capability | Source implemented? | Unit tested? | Integration tested? | Staging deployed? | Production-ready? | Evidence | Known gaps |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Next.js web application | Yes | Existing suite | Existing local evidence only | No evidence | No | `apps/web` and prior repository validation records | Async execution polling/cancellation not wired to the new execution domain |
| FastAPI application | Yes | Existing suite | Existing local evidence only | No evidence | No | `apps/api`; authenticated practice/submission routes | Current Run/Submit path still invokes `LocalFunctionalPythonRunner` synchronously |
| PostgreSQL persistence and migrations | Yes | Tests/config authored | **0009 migration CI job authored, not executed** | No | No | `20260728_0009_execution_queue_foundation.py`; readiness head updated to 0009 | Must run clean upgrade/downgrade/re-upgrade and staging migration |
| OIDC / authorization | Yes | Existing tests | Local only | No | No | normalized principal, permissions, local OIDC/PKCE | Production provider/redirect/session lifecycle and physical-device proof absent |
| Practice sessions | Yes | Existing tests | Local only | No | No | PostgreSQL-backed practice sessions and server drafts | Client async execution lifecycle not integrated |
| Candidate Run API | Legacy source only | Existing local-runner coverage | Local only | No | **No** | existing Run route | Still executes candidate Python in FastAPI; P0 rewrite required |
| Candidate Submit API | Legacy source only | Existing evaluation tests | Local only | No | **No** | existing submission/evidence flow | Still synchronous/local; must submit durable execution and return 202 |
| Canonical execution state machine | **Yes** | **Tests authored** | Not executed | No | No | `execution_domain.py`, `test_execution_domain.py`, state-machine doc | Dispatcher/end-to-end transitions not proven |
| Durable execution idempotency | **Yes foundation** | **Tests authored** | Not executed | No | No | candidate-scoped uniqueness + request fingerprint | Async endpoints still need endpoint-scoped `Idempotency-Key` wiring |
| Transactional execution outbox | **Yes** | **Tests authored** | Not executed | No | No | execution/payload/event/outbox can commit in one transaction | Worker DB role and real SQS publish integration absent |
| Outbox publisher application service | **Yes** | **Tests authored** | Not executed | No | No | injectable publisher port; success/failure/retry behavior | Concrete AWS SQS transport intentionally not added without locked dependency/IAM integration |
| Versioned queue event contract | **Yes** | **Tests authored** | Not executed | No | No | strict Pydantic schema v1, extra fields forbidden, no source code | Real SQS send/receive/redelivery proof absent |
| SQS execution queue + DLQ | **Terraform source implemented** | Terraform CI gate authored | Not executed | **No** | No | encrypted Standard SQS queue, DLQ, redrive, long polling, visibility timeout, IAM policy docs | No `terraform plan/apply`, no live queue metrics/redelivery/DLQ test |
| Atomic execution claim | **Yes** | Lease tests authored | Not executed against PostgreSQL | No | No | compare-and-set `QUEUED -> DISPATCHING`, attempt increment | Must test concurrent dispatchers against real PostgreSQL |
| Execution leases | **Yes foundation** | Lease validation test authored | Not executed against PostgreSQL | No | No | owner/expiry, renew, expired-lease scan | No reconciler yet; no Kubernetes existence check/recovery loop |
| Trusted execution dispatcher | Partial foundations | Component tests authored | No | No | No | event parser, claim repo, sandbox builder | Full consume → claim → create resources → monitor → persist → cleanup loop absent |
| Kubernetes execution boundary | **Source implemented** | Manifest/job tests authored | No cluster validation | No | No | restricted namespace, dedicated no-token service account, RuntimeClass, quota, LimitRange, default-deny | EKS execution nodes and CNI enforcement not deployed |
| gVisor runtime | **Source contract implemented** | Manifest tests authored | **No runtime proof** | No | **No** | `runtimeClassName: gvisor`, `handler: runsc`, `GVISOR_VALIDATION.md` | Must prove actual execution nodes use `runsc` in staging |
| Server-controlled sandbox profiles | **Yes** | Tests authored | No | No | No | python/sql small/large profiles; client cannot choose arbitrary limits | Scheduling/capacity behavior not measured |
| Python sandbox Job builder | **Yes** | Tests authored | No | No | No | non-root, read-only root, caps dropped, seccomp, no SA token, no host namespaces, immutable image requirement | Actual Job creation/cleanup/network denial not proven |
| Versioned Python runner | **Yes, first production-oriented implementation** | **Runner tests authored and collected by pytest** | No gVisor/EKS integration | No | No | pinned runner Dockerfile; bounded child processes/output; hidden expected outputs excluded | Must build/scan/sign image and run adversarial staging suite; runner is not security boundary alone |
| Hidden-test isolation | Partial implementation | Runner tests authored | No | No | No | expected outputs never enter candidate container; hidden stdout/stderr suppressed | Trusted post-sandbox comparator/result sanitizer still required |
| Disposable PostgreSQL candidate SQL | Not yet production implemented | Existing local concepts only | No | No | No | SQL profile placeholders and prior local adapter concepts | Disposable PostgreSQL Job/sidecar lifecycle is still P0 |
| Execution cancellation | Domain/outbox foundation | State tests authored | No | No | No | terminal cancel transition + cancel-requested event | API endpoint, Job deletion, race reconciliation absent |
| Reconciliation service | Expired-lease query only | No full-loop test | No | No | No | expired lease discovery exists | Missing job inspection, repair/fail-safe decisions, orphan cleanup |
| Execution artifact flow | DB payload separation foundation | No integration test | No | No | No | SQS event contains references/metadata rather than source | Production S3 execution artifacts and scoped temporary access absent |
| Result sanitization | Design/runner partial | No end-to-end test | No | No | No | runner normalizes bounded output; gVisor validation doc forbids infra leakage | Trusted sanitizer and public API projection not wired |
| Execution usage accounting | Schema foundation | No | No | No | No | runtime/cpu/memory/result fields added | Runtime collector and usage event emission absent |
| AWS production infrastructure | Partial execution-queue source only | Terraform gate authored | No | No | No | SQS/KMS module and staging composition now exist | VPC, RDS, Valkey, ECS, EKS, ALB, WAF, CloudFront, DNS, Secrets/ECR remain undeployed/incomplete |
| PostgreSQL role separation | Partial | Existing local bootstrap evidence | Local only | No | No | migrator/app/readonly/sql-sandbox roles exist | Dedicated execution publisher/dispatcher DB identity and production Secrets Manager bootstrap required |
| One-shot migration runner | Local Compose only | Existing local path | No production deployment | No | No | local `migrate` service | ECS one-shot migration task and deploy gate absent |
| CI | **Workflow source implemented** | N/A | **No workflow run evidence** | N/A | No | Python, web, migration and Terraform validation jobs authored | Connector pushes did not produce Actions runs; security scans/SBOM/signing/deploy stages remain |
| Expo / React Native application | **Not evidenced on inspected GitHub branch** | Not evidenced | Not evidenced | No | No | current multiplatform audit does not support prior ~80% claim | Re-audit any unpublished/local mobile work before claiming implementation |
| iOS / iPadOS physical E2E | No evidence | No | No | No | No | device evidence absent | Login/editor/Run/Submit/background/recovery testing required |
| Android phone/tablet physical E2E | No evidence | No | No | No | No | device evidence absent | Same physical-device validation gap |
| Observability / alerting | Partial platform foundation | Limited | No execution-plane proof | No | No | trace_id/correlation fields in execution domain | Required metrics, dashboards, alarms and structured execution events incomplete |
| Supply-chain security | Partial | No pipeline proof | No | No | No | pinned runner base image and immutable runtime-reference rule | Trivy/Syft/Cosign/dependency review/image signing not implemented end-to-end |
| Backup/PITR recovery | No staging evidence | No | No | No | No | requirement documented | Restore exercise/RTO/RPO evidence absent |
| Load/concurrency/failure injection | No production evidence | No | No | No | No | requirements documented | 10/50/100/500 tests, 500-request burst and failure scenarios remain |

## Implemented in this execution-plane slice

1. Canonical durable execution lifecycle with explicit legal transitions.
2. Request fingerprinting and durable idempotency foundation.
3. Execution payload separation and transactional outbox in migration `0009`.
4. Concurrent outbox claiming with `FOR UPDATE SKIP LOCKED`, retry/backoff/jitter, and an injectable queue publisher service.
5. Strict schema-versioned execution queue events that reject source-code payloads and unknown fields.
6. Atomic dispatcher claims, leases, lease renewal, Kubernetes Job identity tracking, and expired-lease discovery.
7. Encrypted SQS execution queue + DLQ Terraform module with redrive policy and least-privilege IAM policy documents.
8. Staging Terraform composition for the execution queue, without claiming it has been applied.
9. gVisor execution namespace source: restricted Pod Security, `runsc` RuntimeClass, no-token service account, deny-all network policy, quota and limit range.
10. Server-controlled Python/SQL resource profiles and hardened Python Job manifest generation.
11. A versioned, pinned Python runner image and bounded runner process that excludes hidden expected answers from the candidate sandbox.
12. Unit/security test source for transitions, events, outbox retry, publisher behavior, leases, sandbox manifests and the Python runner.
13. CI source for Python, Web, clean PostgreSQL migration cycle and Terraform format/validation.
14. Explicit staging gVisor validation gate that remains pending until real `runsc` evidence exists.

## Immediate blockers

### P0

- Rewire Run/Submit to durable async execution and return `202 Accepted`; FastAPI must stop executing candidate code in production mode.
- Add dedicated trusted execution-worker database identity/policies and concrete SQS transport/consumer.
- Complete the dispatcher lifecycle: create input resource + NetworkPolicy + Job, monitor, collect, sanitize, persist terminal result, clean up, and acknowledge queue message.
- Implement reconciliation for expired leases, missing/completed Jobs, orphan resources and cancellation races.
- Implement disposable PostgreSQL SQL execution and fixture lifecycle.
- Implement/deploy VPC/EKS execution nodes with actual gVisor and prove `runsc` in staging.
- Run the authored tests and migration/Terraform gates; current connector-originated commits have no Actions evidence.

### P1

- Async Web/native polling, cancellation and background/resume recovery.
- S3 execution-artifact flow with execution-scoped access.
- DLQ inspect/replay workflow.
- Adversarial sandbox and failure-injection suites.
- Metrics, dashboards and alerts.
- Full AWS control-plane Terraform and one-shot migration deployment.
- Build/scan/SBOM/sign runner images using immutable git-SHA/digest references.

### P2

- Load/cost benchmarking and autoscaling/backpressure tuning.
- Mock Interview durable domain only after the shared execution plane is healthy.

No capability is marked production-ready merely because source code exists.
