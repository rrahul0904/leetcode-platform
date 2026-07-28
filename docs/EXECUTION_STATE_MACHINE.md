# Rigor production execution state machine

## Target states

```text
QUEUED
DISPATCHING
RUNNING
COMPLETED
FAILED
TIMEOUT
CANCELLED
INFRASTRUCTURE_ERROR
```

The current database enum predates this production state model and still uses `RUNNING`, `PASSED`, `FAILED`, `ERROR`, and `TIMED_OUT` terminal naming. That schema must be migrated deliberately as part of the async dispatcher milestone; this branch does not mislabel the existing synchronous implementation as the target state machine.

## Target transitions

```text
QUEUED
  -> DISPATCHING
  -> CANCELLED
  -> INFRASTRUCTURE_ERROR

DISPATCHING
  -> RUNNING
  -> CANCELLED
  -> INFRASTRUCTURE_ERROR

RUNNING
  -> COMPLETED
  -> FAILED
  -> TIMEOUT
  -> CANCELLED
  -> INFRASTRUCTURE_ERROR
```

Terminal states are immutable during normal processing.

## Delivery/idempotency

SQS may redeliver. A trusted worker must atomically claim an execution using a persisted lease/attempt identifier. Receiving a message for an already-terminal execution acknowledges the message without launching code.

The API transaction should create the execution request and an outbox record together. A publisher sends `execution_id` to SQS and records delivery. Candidate source/hidden tests are retrieved through trusted storage rather than copied into the queue body.

## Reconciliation

A periodic trusted reconciliation process must detect impossible/stale combinations such as a long-running database state with no Kubernetes Job and deterministically move them to an infrastructure terminal state after the lease/deadline rules expire.

## Client contract

Clients never set execution status. They read canonical backend state via stream/polling APIs. Socket loss is not a correctness event; reconnect/refetch restores state.
