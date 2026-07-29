# Rigor Platform Production Readiness Scorecard

Updated: 2026-07-29

These percentages are engineering estimates, not deployment claims. Implementation measures source coverage of the target architecture. Validation measures executed evidence. Production readiness discounts source and CI work heavily until representative AWS/EKS/gVisor behavior is proven live.

GitHub Actions run **234** (`30424496509`) passed the current execution-plane checkpoint across Python, Web, PostgreSQL migration cycle, and Terraform source validation.

| Category | Implementation % | Validation % | Production-readiness % | Current evidence | Dominant blocker |
| --- | ---: | ---: | ---: | --- | --- |
| Product functionality | 78 | 60 | 42 | Web practice Run/Submit now use durable async execution contract; CI green | Staging execution and native client gap |
| Web readiness | 88 | 72 | 52 | Async queue/poll/recovery/cancel integrated; lint/type/test/build green | Real browser E2E against staging execution plane |
| Mobile readiness | 15 | 0 | 0 | Shared server execution contract is client-neutral | Expo/native workspace and physical-device execution flow not evidenced |
| API readiness | 90 | 78 | 55 | Canonical async Run/Submit/Status/Cancel, idempotency, sanitized DTOs, HTTP integration tests | Staging and cross-candidate real app-role verification |
| Data durability | 88 | 74 | 54 | PostgreSQL execution records, payload, events, outbox, leases, result tables, RLS; migration `0011` cycle green | Production RDS/PITR/restore and role provisioning |
| Execution safety | 82 | 48 | 28 | no-token hardened Job source, server-owned limits, runner/result hardening, hidden-test separation | Live EKS/runsc and adversarial proof |
| Execution reliability | 80 | 55 | 34 | outbox retry, SQS client, atomic claim, leases, attempt fencing, reconciliation controller | Real SQS/K8s failure injection and complete recovery matrix |
| Security | 75 | 52 | 32 | candidate RLS, NOBYPASSRLS worker roles, bounded protocol, no source in queue, sandbox source controls | Live network/IAM isolation, image signing/scanning, hostile staging tests |
| Infrastructure | 38 | 20 | 8 | SQS/KMS/DLQ Terraform validates; K8s controller/boundary source exists | No applied representative AWS execution environment |
| Observability | 32 | 16 | 10 | execution/trace/attempt fields and structured controller logging | Metrics, tracing backend, dashboards and alerts |
| Disaster recovery | 12 | 0 | 0 | durable architecture/reconciliation foundations | No RDS restore, queue recovery or RTO/RPO exercise |
| Performance | 18 | 5 | 2 | bounded profiles/backpressure foundations | No controlled 10/50/100/500 benchmark or capacity data |
| CI/CD | 82 | 78 | 48 | run 234 passed Python/Web/migration/Terraform jobs | Deploy/security/SBOM/signing stages absent |
| SQL execution | 15 | 0 | 0 | schema/content concepts and sandbox profiles only | Disposable PostgreSQL execution pipeline not implemented |
| Release readiness | 52 | 38 | 22 | Strong application baseline and CI-validated Python async execution source | No staging execution proof, SQL/mobile gaps |

## Overall engineering estimate

- Overall implementation: **72%**
- Overall validation: **45%**
- Overall production readiness: **28%**
- Production execution-plane implementation: **82%**
- Production execution-plane validation: **48%**
- Staging deployment/validation: **0%**

## Interpretation

### Implementation

The production-oriented Python execution vertical slice is now substantially wired in source: canonical `202` APIs, durable execution/outbox, SQS transport, trusted controller, Kubernetes sandbox adapter, bounded runner, trusted comparator, persistence, cancellation/reconciliation foundations, and async Web consumption. SQL and native mobile execution remain material source gaps.

### Validation

Validation increased materially because the branch now has an actual green GitHub Actions run. CI proves repository semantics and source integration, including HTTP/DB execution creation and migration/role correctness. It does **not** prove AWS SQS delivery, EKS scheduling, gVisor/runtime isolation, CNI/SG egress blocking, AWS credential isolation, or hostile workload containment.

### Production readiness

Production readiness remains intentionally lower. The next large increase should occur only after a real request crosses:

```text
Web/API → PostgreSQL/outbox → SQS → controller → EKS/runsc → Python runner
→ trusted evaluator → PostgreSQL → polling client
```

and the same environment passes duplicate-delivery, crash/reconciliation, cancellation-race, network isolation, credential isolation, timeout, memory/process, and output-flood tests.

A Terraform/Kubernetes source file remains **SOURCE IMPLEMENTED** or **CI VALIDATED SOURCE**, never **STAGING VALIDATED**, until deployed evidence exists.
