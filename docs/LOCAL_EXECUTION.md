# Local Docker Execution

## Purpose

The local execution path makes Python and PostgreSQL Run/Submit workflows usable without AWS, SQS, Kubernetes, or gVisor. It preserves the same durable application state machine used by the production design, but Docker Compose is a development boundary and is not equivalent to production sandbox isolation.

## Flow

```text
Next.js Web
    |
    v
FastAPI asynchronous execution API
    |
    v
Application PostgreSQL
  execution_requests
  execution_payloads
  execution_outbox
  local_execution_queue
    |
    v
Local execution controller
    |-----------------------|
    v                       v
Python runner            SQL runner
restricted subprocess    disposable fixture database
                            |
                            v
                     execution-postgres
                     no application data
    |-----------------------|
    v
Trusted result parser and comparator
    |
    v
Durable public result and event history
```

## Durable queue

`local_execution_queue` provides local message visibility and receipt semantics. The controller publishes the existing transactional outbox into this queue, claims execution leases, dispatches work, persists results, and reconciles stale executions.

Restarting the controller does not remove queued requests or durable results. Queue messages become visible again after their visibility timeout.

## Python runner

The Python service:

- accepts requests only on the internal execution network;
- validates bounded JSON input;
- reuses the existing Python 3.13 runner contract;
- creates a restricted subprocess for each test;
- applies time, process, file-size, and output limits;
- separates public and hidden test visibility;
- returns a bounded structured result;
- runs as a non-root user with a read-only root filesystem, dropped capabilities, bounded memory, CPU, and process count.

It receives no application database credentials, cloud credentials, host mount, or Docker socket.

## SQL runner

The SQL service connects only to `execution-postgres`, a separate internal PostgreSQL instance containing no application data. It:

- recreates the execution database and candidate role for each test;
- loads only question fixture DDL and seed data;
- enforces statement and timeout policy;
- compares candidate rows to trusted expected rows;
- normalizes supported values while preserving duplicates and ordering policy;
- serializes local SQL executions to prevent fixture replacement races.

The execution database is stored on `tmpfs` and is disposable.

## Controller health

The controller writes a heartbeat to `local_execution_controller_status`, including:

- current queue depth;
- Python runner availability;
- SQL runner availability.

API readiness fails when `LOCAL_DOCKER` is selected and the heartbeat is missing or stale, or either runner is unavailable.

## Cancellation and interruption

Cancellation uses the existing durable cancellation event and controller contract. A local in-flight HTTP request cannot forcibly kill an already running thread from outside the runner; the bounded runner timeout remains the final local stop condition. The production Kubernetes path can delete the sandbox Job directly.

## Security boundary

The local path is appropriate for trusted development machines and functional testing. It must not be exposed as a public multi-tenant execution service. Production requires the repository's Kubernetes/gVisor execution plane, hostile-execution nodes, network policy, cloud queue, credential isolation, and adversarial staging evidence.
