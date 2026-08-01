# Execution DLQ Runbook

Updated: 2026-07-30

## Safety model

The DLQ is not an alternative execution-state store. PostgreSQL remains authoritative. Never redrive all DLQ messages blindly.

Operator tooling is implemented in `rigor_api.execution_dlq` and classifies each message against the durable execution row before taking action.

Required environment:

```text
RIGOR_EXECUTOR_DATABASE_URL
RIGOR_EXECUTION_QUEUE_URL
RIGOR_EXECUTION_DLQ_URL
AWS_REGION
```

Use the trusted execution-operator identity. Never run these commands with candidate workload credentials.

## Inspect

```bash
python -m rigor_api.execution_dlq inspect --limit 10
```

Inspection returns messages to the DLQ immediately after classification.

Possible dispositions:

- `REPLAY`: safe to send to the primary queue;
- `DISCARD_TERMINAL`: durable state proves no replay is needed;
- `HOLD_IN_PROGRESS`: execution is already claimed/running;
- `HOLD_UNKNOWN`: no durable execution row exists;
- `HOLD_MALFORMED`: event cannot be safely parsed.

## Replay

```bash
python -m rigor_api.execution_dlq replay --limit 10
```

`execution.requested` replays only when PostgreSQL still says `QUEUED`.

A requested event for DISPATCHING/RUNNING is held. A requested event for COMPLETED/FAILED/TIMEOUT/CANCELLED is not replayed.

A cancellation event replays only when the durable execution is CANCELLED and still records a Kubernetes Job that requires cleanup.

Successful replay sends the exact versioned event body to the primary queue and deletes the DLQ copy. Candidate source and hidden expected answers are never reconstructed into the queue event.

## Discard proven terminal messages

```bash
python -m rigor_api.execution_dlq discard-terminal --limit 10
```

Only `DISCARD_TERMINAL` messages are deleted. Unknown, malformed, replayable, or in-progress messages remain in the DLQ.

## Investigation rules

For `HOLD_UNKNOWN`, first determine whether the message references a deleted/test environment or indicates database loss. Do not create a replacement execution row from the queue message.

For `HOLD_MALFORMED`, retain the message until its producer/version/source is identified. Do not edit malformed payloads manually and replay them as candidate work.

For `HOLD_IN_PROGRESS`, inspect the current lease and Kubernetes Job. Let the reconciler converge before manual intervention.

## Acceptance test

Before production sign-off, inject one message for each disposition and verify that:

1. terminal candidate work is never restarted;
2. queued work can be replayed idempotently;
3. in-progress work is not duplicated;
4. cancellation cleanup can be retried;
5. malformed/unknown messages remain available for investigation.
