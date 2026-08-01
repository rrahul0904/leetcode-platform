# Execution Reconciliation Runbook

Updated: 2026-07-30

## Purpose

Recover durable candidate executions after controller, SQS, Kubernetes, node, or transient database failures without running candidate work twice or reopening terminal executions.

PostgreSQL `execution_requests` is authoritative. SQS delivery and Kubernetes Job existence are observations, not execution truth.

## Core invariants

- A delivery may claim only `QUEUED -> DISPATCHING` atomically.
- Claims carry a worker, lease deadline, and incremented attempt.
- Terminal states never return to QUEUED, DISPATCHING, or RUNNING.
- Terminal persistence requires the current lease owner + attempt under a row lock.
- A worker that loses its lease must not delete a sandbox another worker may have adopted.
- Missing-sandbox retries are bounded by the configured maximum attempt count.

## Automated reconciliation

The controller periodically:

1. republishes stale QUEUED execution outbox events whose prior queue delivery did not result in a claim;
2. scans expired DISPATCHING/RUNNING leases using `FOR UPDATE SKIP LOCKED`;
3. observes the durable Kubernetes Job identity when present;
4. adopts live Jobs by renewing ownership rather than launching duplicates;
5. persists results for completed Jobs;
6. starts a fresh bounded attempt when an expired execution has no sandbox and retry budget remains;
7. converges to sanitized `FAILED / INFRASTRUCTURE_ERROR` after retry exhaustion;
8. removes orphaned Jobs for already-terminal executions.

## Failure matrix

| Durable state | Kubernetes state | Action |
| --- | --- | --- |
| QUEUED | none | outbox/SQS republish if stale |
| DISPATCHING/RUNNING, lease live | any | current owner remains authoritative |
| DISPATCHING, lease expired | live Job | reacquire lease; record/run as appropriate |
| RUNNING, lease expired | live Job | reacquire lease and continue observing |
| DISPATCHING/RUNNING, lease expired | completed Job | reacquire and persist trusted result |
| DISPATCHING/RUNNING, lease expired | missing Job | start next infrastructure attempt if budget remains |
| DISPATCHING/RUNNING, lease expired | missing Job, retry exhausted | terminal infrastructure failure |
| terminal | orphan Job | delete Job/Secret/NetworkPolicy idempotently |
| terminal | duplicate SQS event | ACK/no candidate rerun |

## Operator checks

Inspect a single execution in PostgreSQL:

```sql
SELECT id, state, attempt_count, lease_owner, lease_expires_at,
       kubernetes_namespace, kubernetes_job_name, error_category
FROM execution_requests
WHERE id = '<execution-id>';
```

Inspect the Job only when the durable row provides its identity:

```bash
kubectl -n rigor-execution get job <job-name> -o yaml
kubectl -n rigor-execution get pods -l job-name=<job-name> -o wide
```

Do not manually set an execution back to `QUEUED` to recover it. Do not manually send candidate source through SQS. Do not delete a live Job before confirming durable ownership/attempt and terminal/cancel state.

## Failure injection before staging sign-off

Exercise at least:

- duplicate `execution.requested` delivery;
- controller termination immediately after claim;
- controller termination after Job creation;
- controller termination after Job completion before result persistence;
- result persistence before SQS ACK;
- lease expiry with live Job;
- lease expiry with missing Job;
- malformed/wrong-attempt result;
- Kubernetes API transient failure;
- PostgreSQL transient failure;
- cancellation racing Job completion.

CI currently proves duplicate-claim single-winner semantics, old-attempt fencing, retry-attempt advancement, and retry bounds. Live controller/Kubernetes crash injection remains a staging requirement.
