# Next milestone: durable queued execution

This is the next implementation slice required before staging ECS application compute can be enabled.

## Backend schema

- migrate execution states to `QUEUED`, `DISPATCHING`, `RUNNING`, `COMPLETED`, `FAILED`, `TIMEOUT`, `CANCELLED`, `INFRASTRUCTURE_ERROR`;
- preserve legacy state migration semantics;
- add durable outbox records and publish timestamps/attempt metadata;
- add lease/attempt fields needed for atomic worker claims and reconciliation.

## API

Run/Submit transactions create submission/execution/outbox state and return canonical queued representations without executing source in FastAPI.

Expose status retrieval and cancellation. Streaming is an optimization; polling must remain sufficient for correctness.

## Publisher

A trusted publisher reads committed outbox rows, sends `{execution_id}` to SQS, records publish success idempotently, and retries without duplicating business state.

## Dispatcher

A trusted ECS worker receives IDs, atomically claims eligible executions, creates a gVisor Job, observes bounded execution, sanitizes results, persists evaluation/evidence/readiness where appropriate, and acknowledges the queue message.

Terminal executions are never re-run when SQS redelivers.

## Kubernetes

Use the existing restricted namespace/RuntimeClass/network policy and create per-execution Jobs. Python uses the approved runtime image; SQL includes disposable PostgreSQL and a restricted role. Candidate pods receive no AWS/application credentials.

## Reconciliation

A periodic trusted process closes stale leases/orphaned Jobs, enforces deadlines, and cleans leftover Jobs/artifacts.

## Acceptance

Implement adversarial tests for duplicate messages, worker crash points, timeout/OOM, Job launch failure, result-persistence failure, cancellation races, no network/metadata/RDS/Valkey access, output bounds, and cleanup.
