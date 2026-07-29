# Rigor Platform Implementation Audit

Audit date: 2026-07-29

This audit is based on `feature/rigor-multiclient-infrastructure` and intentionally separates source implementation, CI validation, staging validation, and production readiness. Source files, Terraform, Kubernetes YAML, and tests are not deployment evidence by themselves.

## Branch evidence

At the code-validation checkpoint before this audit update, the branch was **136 commits ahead of `main` and 0 behind**. Base SHA: `2e45d43b09ac98d9c184923d4d84182ba4d36f89`.

GitHub Actions run **234** (`30424496509`) passed all four repository CI jobs for the execution-plane code checkpoint:

- Python: locked workspace install, PostgreSQL startup/migration/seed, Ruff, strict Pyright, Pytest.
- Web: frozen pnpm install, lint, typecheck, tests, production build.
- Database: fresh upgrade to `20260729_0011`, execution-role checks, downgrade to `0010`, re-upgrade to head.
- Terraform: recursive format check, staging init with backend disabled, validate.

## Capability audit

| Capability | Verified status | Evidence | Remaining validation / blocker |
| --- | --- | --- | --- |
| Canonical Run API | **CI VALIDATED** | `POST /api/v1/questions/{slug}/run` returns `202`; HTTP integration test forbids `LocalFunctionalPythonRunner.execute`, verifies durable execution, payload, outbox, idempotent replay and 409 conflict | Real staging request through SQS/EKS not yet validated |
| Canonical Submit API | **CI VALIDATED** | `POST /api/v1/questions/{slug}/submissions` returns `202`, creates linked submission and uses same durable execution service; HTTP test forbids local runner | Full staging hidden evaluation and readiness update not yet validated |
| Execution status API | **CI VALIDATED** | `GET /api/v1/executions/{id}` uses candidate RLS context and returns sanitized DTO with attempt/runtime/memory/result/error | Cross-candidate behavior still needs explicit non-superuser integration proof and staging verification |
| Cancellation API | **CI VALIDATED foundation** | Idempotent terminal behavior, durable cancel event/domain transition, HTTP auth contract, controller Job cleanup path | Live DISPATCHING/RUNNING completion-vs-cancel race on EKS not yet proven |
| Production local-runner fail closed | **CI VALIDATED** | deployable environments reject `LOCAL_FUNCTIONAL`; canonical HTTP tests fail if local runner is invoked | Staging configuration must prove Kubernetes adapter is actually used |
| Execution state machine | **CI VALIDATED** | legal/illegal transition and terminal-state tests | Real failure/recovery convergence still needs staging injection |
| Durable idempotency | **CI VALIDATED** | request fingerprint + candidate key; HTTP same request returns same execution, changed request returns 409 | Distributed client retry behavior should be exercised in staging |
| Transactional payload/outbox creation | **CI VALIDATED** | HTTP DB proof verifies QUEUED row, payload and unpublished `execution.requested` outbox event after one request | Live publisher delivery not yet validated |
| Queue event secrecy | **CI VALIDATED** | queue event schema excludes source; HTTP test asserts source absent from outbox/SQS payload; sandbox payload excludes expected answers | Live queue inspection still required |
| SQS transport | **CI VALIDATED against repository test transport** | SigV4 client implements Send/Receive/Delete/ChangeVisibility, long polling, bounded parsing and refreshable trusted credentials | **NOT STAGING VALIDATED** against real AWS SQS/IAM |
| Outbox publisher | **CI VALIDATED component** | `FOR UPDATE SKIP LOCKED`, success/failure/retry/backoff/jitter tests and controller integration | Multi-replica real SQS contention/restart test required |
| Atomic claim and leases | **CI VALIDATED component** | compare-and-set claim, attempt increment, lease renewal, expired lease discovery | Concurrent real dispatcher/PostgreSQL stress test required |
| Old-worker result fencing | **CI VALIDATED source/tests** | terminal persistence requires exact lease owner + attempt under row lock; wrong-attempt runner results rejected | Failure injection with lease transfer in staging required |
| Trusted execution controller | **SOURCE IMPLEMENTED / CI VALIDATED components** | SQS validation, claim, K8s create, RUNNING transition, monitor, trusted evaluation, persistence, cleanup, ACK, heartbeat, reconciliation source | No real SQS → EKS execution yet |
| Reconciliation | **SOURCE IMPLEMENTED / CI VALIDATED components** | expired DISPATCHING/RUNNING scan, K8s observation, lease reacquisition, completed/failed/missing Job handling | Full recovery matrix and orphan-resource tests remain P0 |
| Execution worker DB identity | **CI VALIDATED** | migration `0011`; `rigor_execution_worker`, `rigor_execution_reconciler`, compatibility executor are `NOBYPASSRLS`; explicit grants/RLS policies | Production login provisioning/Secrets Manager/IAM-auth path not deployed |
| Candidate execution RLS | **SOURCE IMPLEMENTED / migration CI VALIDATED** | own-candidate/org policies on execution aggregate and child tables | Explicit second-candidate test under real `rigor_app` login remains |
| Kubernetes sandbox boundary | **SOURCE IMPLEMENTED / CI source tests** | no-token candidate SA, restricted security context, read-only root, caps dropped, seccomp, no host namespaces, server-controlled limits, deny-all NetworkPolicy | **NOT STAGING VALIDATED** |
| gVisor | **SOURCE IMPLEMENTED** | RuntimeClass/Job source requests `gvisor` / `runsc` | **NOT STAGING VALIDATED**; YAML is not proof of runsc |
| Python runner | **CI VALIDATED** | bounded source/tests/output/resources, expected-answer rejection, normal algorithm imports, process-group kill on timeout, protocol tests | Build/scan/sign image and run hostile code on real gVisor nodes |
| Trusted result protocol | **CI VALIDATED** | schema/execution/attempt binding, unique IDs, size/status validation, complete test set for COMPLETED, visibility tamper rejection | Kubernetes log/artifact transport still needs live proof |
| Trusted hidden-test evaluator | **CI VALIDATED** | hidden expected values stay trusted; exact/text/numeric/JSON/unordered strategies are server configured; public projection redacts hidden expectations | More question-schema comparison cases can be added as content expands |
| Result sanitization | **CI VALIDATED foundation** | bounded public stdout/stderr, public tests only, hidden aggregates, sanitized infrastructure/candidate error categories | Staging hostile-output/stack/path leakage validation required |
| Web async execution | **CI VALIDATED** | 202 flow, adaptive polling, terminal stop, localStorage recovery, temporary network retries, cancellation control, production build | Browser staging E2E against real execution plane required |
| Mobile API compatibility | **SOURCE CONTRACT IMPLEMENTED** | server contract is client-neutral and shared execution semantics do not branch by platform | No Expo/native workspace is evidenced on this branch; native polling/recovery is **NOT IMPLEMENTED** |
| Terraform execution queue | **CI VALIDATED source** | SQS/KMS/DLQ module passes fmt/init/validate | Resources have not been applied/verified in AWS |
| SQL sandbox execution | **NOT IMPLEMENTED** | only SQL profile/content concepts exist; controller currently supports Python production dispatch only | Disposable PostgreSQL execution + fixtures + result comparison remain P0 |
| S3 execution artifacts | **NOT IMPLEMENTED** | DB payload/result path handles bounded initial vertical slice | Large/sensitive artifact flow, KMS/lifecycle/signed access remain P1 |
| DLQ operations | **SOURCE INFRASTRUCTURE ONLY** | queue/DLQ/redrive/IAM source exists | Inspect/classify/replay/discard tooling and live redrive test remain |
| Observability | **PARTIAL SOURCE IMPLEMENTED** | trace ID, execution ID, attempt, structured controller fields | Required metrics, tracing export, dashboards and alerts remain |
| Autoscaling / dedicated EKS execution nodes | **NOT IMPLEMENTED / NOT DEPLOYED** | scheduling/security requirements documented in source | KEDA/backlog scaling, execution node group, taints/tolerations and capacity proof remain |
| CI | **CI VALIDATED** | GitHub Actions run 234 passed Python, Web, migration cycle and Terraform jobs | Security scanning, image signing and deploy pipeline stages remain |
| Staging execution slice | **NOT VALIDATED** | no live AWS/EKS evidence available in this implementation session | RDS/SQS/controller/EKS/gVisor/API/Web must execute one real candidate request |

## Security invariants now enforced in code

1. Canonical Run/Submit do not call the local runner in FastAPI; CI tests monkeypatch the local runner to fail if reached.
2. Staging/production configuration rejects `LOCAL_FUNCTIONAL` execution.
3. SQS/outbox execution events do not contain candidate source or hidden expected answers.
4. Candidate sandbox input contains source + test inputs/visibility/IDs, but not expected answers.
5. Candidate Kubernetes Jobs use no service-account token and no AWS workload identity in the supplied manifests.
6. Resource/security settings are server-owned, not candidate-controlled.
7. Duplicate queue deliveries cannot claim a QUEUED execution twice through the normal claim transition.
8. Terminal states have no outgoing transitions back to RUNNING.
9. Terminal result persistence is fenced by active lease owner and attempt.
10. Runner results are bound to execution ID and attempt and are rejected if malformed/incomplete/tampered.

Network and credential isolation are **source-enforced but not staging-proven** until adversarial checks run on the deployed EKS/gVisor execution nodes.

## Remaining P0 blockers

- Deploy the minimum representative AWS staging slice: API/PostgreSQL, SQS/DLQ, controller, EKS execution nodes and Python runner.
- Prove the real runtime uses `runsc` and execute the adversarial network/credential/filesystem/resource suite.
- Exercise real SQS at-least-once delivery, duplicate messages, visibility expiry, controller crashes and database/Kubernetes outages.
- Complete the reconciliation/failure-injection matrix so executions cannot remain nonterminal indefinitely.
- Implement disposable PostgreSQL SQL execution and SQL fixture/result-comparison pipeline; never use application RDS.
- Add explicit second-candidate/non-superuser RLS integration coverage for execution status/cancel.

## Remaining P1 blockers

- S3/KMS execution artifact lifecycle for large or sensitive artifacts.
- DLQ operational CLI/admin workflow with safe idempotent replay.
- Execution metrics, OpenTelemetry export, dashboards and alerts.
- KEDA/autoscaling and dedicated untrusted-execution node group source/deployment.
- Broader AWS application infrastructure, one-shot production migration task, image scan/SBOM/signing.
- Native Expo/iOS/Android execution polling/recovery after the mobile workspace is present.

No capability is marked staging validated or production ready without live environment evidence.
