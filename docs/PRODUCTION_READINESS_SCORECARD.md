# Rigor Platform Production Readiness Scorecard

Updated: 2026-07-30

These percentages are engineering estimates, not deployment claims. Implementation measures source coverage of the target architecture. Validation measures executed evidence. Production readiness heavily discounts source and CI work until a representative AWS/EKS/gVisor environment proves the hostile execution boundary live.

GitHub Actions run **333** (`30562217368`) passed the execution-plane code checkpoint across Python, SQL, Web, PostgreSQL migration cycle, execution image builds, and Terraform source validation. The Python job included **128 passed / 1 skipped** tests plus successful builds of the execution controller, Python runner, and SQL runner images.

| Category | Implementation % | Validation % | Production-readiness % | Current evidence | Dominant blocker |
| --- | ---: | ---: | ---: | --- | --- |
| Product functionality | 84 | 68 | 45 | Web practice supports durable async Python and PostgreSQL Run/Submit with status/recovery/cancel | Staging execution and native-client gap |
| Web readiness | 90 | 75 | 52 | async queue/poll/recovery/cancel integrated; lint/type/tests/build green | Browser staging E2E against real execution plane |
| Mobile readiness | 15 | 0 | 0 | server contract remains client-neutral | native Expo/iOS/Android execution workspace not evidenced |
| API readiness | 94 | 86 | 60 | canonical Run/Submit/Status/Cancel, idempotency, runtime enforcement, sanitization and RLS integration tests | real staging API/RDS/SQS execution |
| Data durability | 90 | 82 | 58 | execution aggregate/outbox/results/leases/RLS, migration cycle, retry fencing and DLQ state authority | production RDS/PITR and credential provisioning |
| Execution safety | 92 | 70 | 38 | hardened Python+SQL runner contracts, no-token gVisor Job source, SQL disposable-DB design, hidden-answer separation, adversarial validator | live EKS/runsc and hostile isolation proof |
| Execution reliability | 90 | 72 | 44 | outbox retry, SQS adapter, atomic claim, leases, attempt fencing, stale queue republish, missing-sandbox retry, retry cap, DLQ-safe replay | real SQS/K8s/controller crash injection |
| Security | 88 | 70 | 42 | real `rigor_app` cross-candidate RLS proof, NOBYPASSRLS workers, bounded result protocols, SQL privilege tests, deny-all sandbox source | live CNI/IAM/network/filesystem isolation and supply-chain controls |
| Infrastructure | 45 | 25 | 10 | SQS/KMS/DLQ Terraform validates; controller/boundary manifests and staging validators exist | representative VPC/RDS/EKS execution stack not provisioned |
| Observability | 35 | 18 | 10 | trace/execution/attempt/state fields and structured controller logs | metric export, tracing backend, dashboards and alerts |
| Disaster recovery | 20 | 12 | 5 | durable reconciliation and state-aware DLQ operator exist | no RDS restore, real queue recovery or RTO/RPO exercise |
| Performance | 20 | 8 | 3 | bounded server profiles/backpressure and execution limits | no controlled concurrency/capacity benchmark |
| CI/CD | 90 | 88 | 55 | run 333 passed Python/SQL/Web/migrations/Terraform and all execution image builds | image scanning/SBOM/signing and deployment promotion absent |
| SQL execution | 88 | 72 | 38 | `postgresql18` API/runtime integration, disposable PostgreSQL runner, privilege/timeouts/result comparison and integration tests | real gVisor sidecar execution and network isolation proof |
| Release readiness | 65 | 50 | 28 | strong CI-validated application/execution source for Python and SQL | no live staging execution proof; native/mobile and ops gaps remain |

## Overall engineering estimate

- Overall implementation: **80%**
- Overall validation: **61%**
- Overall production readiness: **35%**
- Production execution-plane implementation: **93%**
- Production execution-plane validation: **70%**
- Staging deployment/validation: **0%**
- Production verification: **0%**

## Interpretation

### Implementation

The execution service is now a shared durable runtime for Python and PostgreSQL: canonical `202` APIs, PostgreSQL/outbox state, SQS transport, controller/leases/reconciliation, Python runner, disposable SQL runner contract, trusted Python/SQL comparison, cancellation, DLQ operations, Kubernetes sandbox construction, async Web consumption, and fail-closed staging/adversarial validators are implemented in source.

The largest remaining implementation gaps are not another candidate runner. They are the representative AWS staging stack, observability/export, queue-depth autoscaling/capacity, supply-chain promotion controls, and native mobile integration.

### Validation

CI validation materially increased. The current suite proves:

- Python and SQL API queueing through the same execution aggregate;
- Python/SQL runtime mismatch rejection;
- transactional payload/outbox creation and queue secrecy;
- same-key idempotency and conflicting-key rejection;
- cross-candidate isolation using the real `rigor_app` PostgreSQL role;
- single-winner duplicate claim semantics;
- expired missing-sandbox retry, old-attempt fencing and retry bounds;
- Python runner and PostgreSQL 18 SQL runner behavior/security constraints;
- ordered/unordered trusted SQL comparison and hidden-result redaction;
- state-aware DLQ replay classification;
- Kubernetes manifest security/image contracts;
- successful controller/Python/SQL Docker image builds.

CI does **not** prove real AWS SQS delivery, EKS scheduling, gVisor runtime isolation, CNI/security-group egress blocking, AWS credential isolation, disposable PostgreSQL behavior inside EKS, or hostile workload containment.

### Production readiness

Production readiness remains intentionally lower than source and CI validation. The next major increase requires a real request to cross:

```text
Web/API
  -> PostgreSQL + transactional outbox
  -> real AWS SQS
  -> trusted controller
  -> EKS dedicated untrusted node
  -> verified runsc/gVisor
  -> Python or disposable PostgreSQL runner
  -> trusted evaluator
  -> PostgreSQL
  -> client polling
```

The live environment must also pass the repository's staging/runsc and adversarial validators plus duplicate delivery, controller crash, lease expiry, node/Pod failure, cancellation race, and cleanup tests.

Terraform/Kubernetes source remains `CI VALIDATED SOURCE`, never `STAGING VALIDATED`, until that live evidence exists.
