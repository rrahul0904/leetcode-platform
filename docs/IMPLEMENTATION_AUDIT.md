# Rigor Platform Implementation Audit

Audit date: 2026-07-30

This audit is based on `feature/rigor-multiclient-infrastructure` and intentionally separates source implementation, CI validation, staging validation, and production verification. Source files, Terraform validation, Kubernetes manifests, runner tests, and Docker builds are not live AWS/EKS evidence.

## Branch evidence

At the execution-plane code checkpoint, the branch is **186 commits ahead of `main` and 0 behind**. Base SHA: `2e45d43b09ac98d9c184923d4d84182ba4d36f89`. Code-checkpoint SHA: `dcb1a40f037f8653356bb8e6a5163c8c218b2524`.

GitHub Actions run **333** (`30562217368`) passed all four jobs:

- Python: locked workspace install, PostgreSQL migration/seed, Ruff, strict Pyright, **128 passed / 1 skipped** Pytest suite, and Docker builds for the Python runner, SQL runner, and execution controller.
- Web: frozen pnpm install, lint, typecheck, tests, and production build.
- Database: fresh upgrade to `20260729_0011`, execution-role checks, downgrade to `0010`, and re-upgrade to head.
- Terraform: recursive format check, staging initialization with remote backend disabled, and validate.

## Capability audit

| Capability | Verified status | Evidence | Remaining validation / blocker |
| --- | --- | --- | --- |
| Canonical Run API | **CI VALIDATED** | `POST /api/v1/questions/{slug}/run` returns `202`; integration tests prove durable execution/payload/outbox, idempotent replay/conflict behavior, Python and SQL runtime selection, and no local runner invocation | Real AWS staging request through SQS/EKS remains |
| Canonical Submit API | **CI VALIDATED** | `POST /api/v1/questions/{slug}/submissions` creates linked submission and uses the same execution aggregate/queue/controller | Staging hidden evaluation/readiness update remains |
| Execution status API | **CI VALIDATED** | sanitized execution DTO with attempt/runtime/memory/result/error; real `rigor_app` RLS test hides another candidate's execution | Staging authorization check remains |
| Cancellation API | **CI VALIDATED foundation** | durable cancel event/domain transition, terminal idempotence, cross-candidate denial, controller cleanup path | Live RUNNING completion-vs-cancel race remains |
| Production local-runner fail closed | **CI VALIDATED** | deployable environments reject `LOCAL_FUNCTIONAL`; canonical HTTP tests fail if local runner is invoked | Staging config must prove Kubernetes execution is active |
| Execution state machine | **CI VALIDATED** | legal/illegal transition and terminal-state tests | Live crash/recovery convergence remains |
| Durable idempotency | **CI VALIDATED** | same principal/key/request returns same execution; changed request with same key returns conflict | Distributed retry behavior remains staging evidence |
| Transactional payload/outbox | **CI VALIDATED** | execution, payload, initial event and outbox event are persisted as one durable request path | Live publisher/SQS delivery remains |
| Queue event secrecy | **CI VALIDATED** | source and hidden expected answers are absent from SQS/outbox event contracts; Python/SQL sandbox payloads exclude expected answers | Live queue inspection remains |
| SQS transport | **CI VALIDATED component** | SigV4 Send/Receive/Delete/ChangeVisibility, long polling, bounded parsing, temporary credential support | **NOT STAGING VALIDATED** against real AWS SQS/IAM |
| Outbox publisher | **CI VALIDATED component** | `FOR UPDATE SKIP LOCKED`, concurrent-safe claim, publish success/failure, backoff/jitter | Multi-controller real SQS contention/restart test remains |
| Atomic claim and leases | **CI VALIDATED** | duplicate delivery test proves one claim winner; lease renewal/expiry and attempt increment tested against PostgreSQL | Multi-replica staging stress remains |
| Old-worker result fencing | **CI VALIDATED** | terminal persistence requires current lease owner + attempt under lock; recovery test proves old attempt loses authority | Controller-kill staging injection remains |
| Trusted execution controller | **SOURCE IMPLEMENTED / CI VALIDATED components** | shared Python/SQL dispatch, SQS validation, claim, K8s create/observe, RUNNING transition, heartbeat, trusted evaluation, persistence, cleanup and ACK | No real SQS -> EKS execution yet |
| Reconciliation | **CI VALIDATED core / SOURCE IMPLEMENTED full controller** | stale QUEUED republish, duplicate claim protection, expired missing-sandbox retry, attempt fencing, retry cap, live/completed/missing Job paths, terminal orphan cleanup | Full controller/Kubernetes crash matrix remains staging validation |
| Execution worker DB identity | **CI VALIDATED** | migration `0011`; worker/reconciler/compatibility executor are `NOBYPASSRLS` with explicit grants/policies | Production login/Secrets Manager or IAM auth provisioning remains |
| Candidate execution RLS | **CI VALIDATED** | Candidate B receives 404 for Candidate A execution/cancel; direct transaction under actual `rigor_app` role sees zero A-owned execution/payload/events/outbox/result/submission rows | Staging identity-provider/RDS proof remains |
| Python runner | **CI VALIDATED** | bounded source/tests/output/resources, expected-answer rejection, process-group timeout kill, protocol validation; image builds in CI | Scan/sign/publish image and hostile live gVisor run remain |
| SQL runtime/API integration | **CI VALIDATED** | `postgresql18` uses the same Run/Submit/execution state machine; Python/SQL runtime mismatch rejected; durable SQL execution uses `language=sql` and server profile | Live EKS SQL execution remains |
| SQL runner | **CI VALIDATED locally** | PostgreSQL 18 integration tests cover SELECT/JOIN/aggregate/CTE/window functions, NULL/numeric normalization, timeout, multiple-command rejection and privilege attacks; image builds in CI | Disposable PostgreSQL sidecar must be proven live under EKS/gVisor |
| SQL database isolation | **CI VALIDATED local contract / SOURCE IMPLEMENTED sandbox** | execution-local owner/candidate credentials, non-superuser candidate role, app-DB connection denial test, K8s ephemeral database and secret source | Live network/RDS isolation remains |
| Trusted SQL comparator | **CI VALIDATED** | ordered/unordered policies, column order, row order, duplicates, NULL/numbers and hidden-result redaction tested | Additional content-specific policies may be added later |
| Trusted result protocol | **CI VALIDATED** | execution ID + attempt binding, unique IDs, bounded result, complete test set for COMPLETED, visibility tamper rejection | Live Kubernetes log/result transport remains |
| Kubernetes sandbox boundary | **CI VALIDATED SOURCE** | gVisor Job source, no candidate token, restricted security contexts, deny-all network, resource limits, no host namespaces, untrusted-node selector/toleration; manifest tests pass | **NOT STAGING VALIDATED** |
| gVisor validation tooling | **CI VALIDATED SOURCE** | fail-closed validator requires digest-pinned probe, RuntimeClass handler `runsc`, dedicated node labels, restricted namespace/SA/network, and live `dmesg` evidence | Script has not been run against live EKS; `runsc` is **NOT PROVEN** |
| Adversarial isolation tooling | **CI VALIDATED SOURCE** | live probe script checks gVisor, AWS credential-provider env, K8s token, read-only root, IMDS, Internet, Kubernetes API, public DNS and configured internal targets | Requires live staging execution nodes |
| DLQ operations | **CI VALIDATED component** | state-aware inspect/replay/discard-terminal; queued requested events replay, in-progress work held, terminal work not restarted, malformed/unknown held | Real SQS DLQ injection/redrive remains |
| Web async execution | **CI VALIDATED** | 202 flow, adaptive polling, terminal stop, localStorage recovery, retry and cancellation; production build passes | Browser staging E2E remains |
| Mobile API compatibility | **SOURCE CONTRACT IMPLEMENTED** | server execution contract is client-neutral | Native Expo/iOS/Android execution flow is not evidenced on this branch |
| Terraform execution queue | **CI VALIDATED SOURCE** | SQS/KMS/DLQ module passes fmt/init/validate | Resources are not applied/verified in AWS |
| Execution controller deployment manifest | **CI VALIDATED SOURCE** | trusted controller RBAC/security context and Python/SQL/PostgreSQL immutable-image configuration contract covered by tests | Controller not deployed in staging |
| Execution images | **CI VALIDATED BUILDS** | controller, Python runner and SQL runner Dockerfiles build in run 333 with the required build CA secret | ECR push, vulnerability scan, SBOM/signing and deployment remain |
| Observability | **PARTIAL SOURCE IMPLEMENTED** | trace ID, execution ID, attempt, state transitions and structured controller logs | execution metric export, tracing backend, dashboards and alerts remain before staging sign-off |
| Autoscaling / execution node capacity | **PARTIAL SOURCE CONTRACT** | candidate Jobs require dedicated `workload=untrusted-execution` + `rigor.io/gvisor=true` nodes | EKS execution node group and queue-depth autoscaling are not implemented/deployed |
| CI | **CI VALIDATED** | run 333 passed Python/Web/migration/Terraform plus all three execution image builds | image scanning/SBOM/signing and deploy stages remain |
| Staging execution slice | **NOT VALIDATED** | executable staging/runsc/adversarial validators now exist | representative VPC/RDS/SQS/controller/EKS/gVisor environment is not available in this session |

## Security invariants enforced in code

1. Canonical Run/Submit never execute candidate Python or SQL inside FastAPI.
2. Staging/production reject the local functional execution adapter.
3. PostgreSQL is execution authority; SQS is at-least-once transport only.
4. Candidate source and hidden expected answers are excluded from queue events.
5. Python and SQL sandbox inputs contain only source plus required test/setup inputs, never trusted expected answers.
6. Candidate Kubernetes Jobs have no service-account token or AWS workload identity in supplied manifests.
7. CPU, memory, ephemeral storage, timeout, image and runtime class are server-controlled.
8. Duplicate queue deliveries cannot win the same QUEUED claim twice.
9. Terminal states cannot reopen.
10. Result persistence is fenced by active lease owner and attempt.
11. Missing-sandbox infrastructure recovery creates a new bounded attempt and fences the old worker.
12. Candidate RLS is proven under `rigor_app`, not only by application WHERE clauses.
13. SQL candidate role cannot create roles/databases or use privileged server operations in local integration tests.
14. DLQ replay consults durable database state and cannot blindly restart terminal executions.

Network, credential, filesystem and runtime isolation remain **source-enforced but not staging-proven** until the live validators pass on the deployed EKS/gVisor environment.

## Remaining P0 blockers

- Provision/deploy the minimum representative AWS staging slice: application API/RDS connectivity, real SQS/DLQ, execution controller, EKS control plane, dedicated untrusted execution node group, immutable runner images and gVisor/runsc configuration.
- Run `scripts/validate_execution_staging.py` and retain live `runsc` proof.
- Run `scripts/validate_execution_isolation.py` against IMDS, Internet/DNS, Kubernetes API and the real staging API/RDS/Valkey endpoints.
- Execute real SQS/controller/Kubernetes failure injection: duplicate/visibility expiry, controller kill after claim/Job/result, Pod eviction/node loss, transient DB/Kubernetes outage and cancel-vs-completion race.
- Add execution metric export/dashboards/alerts required for staging sign-off.

## Remaining P1 blockers

- S3/KMS execution artifact lifecycle for large or sensitive artifacts.
- KEDA/queue-depth autoscaling and production capacity/load testing.
- ECR scan, SBOM generation, signing/attestation and deployment promotion policy.
- RDS restore/PITR and formal RTO/RPO exercises.
- Native Expo/iOS/Android execution polling/recovery when the mobile workspace is present.
- Broader SaaS infrastructure such as CDN/DNS/store-release work after the execution plane is proven.

No capability is marked `STAGING VALIDATED` or `PRODUCTION VERIFIED` without live environment evidence.
