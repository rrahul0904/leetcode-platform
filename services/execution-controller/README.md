# Execution controller

This is the trusted orchestration boundary between at-least-once queue delivery and untrusted Kubernetes Jobs. It never executes candidate source locally.

## Implemented foundations

The current branch now provides reusable controller primitives in `apps/api/src/rigor_api`:

- strict versioned execution queue events;
- transactional outbox claiming and retry behavior;
- atomic `QUEUED -> DISPATCHING` compare-and-set claiming;
- dispatcher leases and renewal;
- expired-lease discovery for reconciliation;
- canonical execution transition validation;
- server-controlled sandbox profiles;
- hardened gVisor Job construction;
- default-deny per-execution network policy construction;
- a bounded versioned Python runner image.

## Still required before this service is production-capable

- dedicated trusted worker database role/policies;
- concrete SQS publisher/consumer adapter;
- Kubernetes client adapter that creates input Secret, NetworkPolicy, Job and cleanup resources idempotently;
- result-log collection and trusted correctness comparison;
- terminal-state persistence and usage event emission;
- cancellation handling;
- reconciliation loop;
- DLQ tooling;
- metrics/tracing;
- EKS/gVisor staging proof.

The controller must treat duplicate SQS delivery and Kubernetes `AlreadyExists` as normal recovery conditions, not as permission to execute twice.
