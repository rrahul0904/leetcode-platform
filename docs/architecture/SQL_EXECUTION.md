# SQL Execution Architecture

Updated: 2026-07-30

## Status

SQL execution is implemented as a runtime of the existing durable execution plane. It does not have a separate public API, queue, state machine, controller, or application database connection path.

Current validation status:

- SQL request/runtime normalization: CI validated.
- SQL runner against PostgreSQL 18 integration service: CI validated.
- SQL Kubernetes Job construction/security controls: CI validated source.
- Disposable PostgreSQL sidecar in EKS/gVisor: not staging validated.
- Live hostile SQL execution in AWS staging: not validated.

## Flow

```text
POST Run / Submit
    -> execution_requests + execution_payloads + execution_outbox
    -> SQS
    -> trusted execution controller
    -> gVisor Kubernetes Job
       |- sql-runner
       `- disposable PostgreSQL 18
    -> bounded actual result
    -> trusted expected-result comparator
    -> execution_public_results
    -> GET execution
```

The application RDS instance is never used as the candidate SQL database.

## Runtime contract

The public runtime is `postgresql18`. Runtime selection is checked against trusted published question content. A Python question cannot be executed as PostgreSQL and a SQL question cannot be executed as Python.

The durable execution stores `language=sql` and a server-controlled sandbox profile such as `sql-small`.

## Trusted content

Trusted question content supplies schema DDL, seed data, statement timeout, public/hidden test inputs, expected outputs, and ordered/unordered result-comparison policy.

Expected outputs remain in the trusted control plane. The candidate sandbox receives only candidate SQL plus trusted schema/fixture inputs required to construct the disposable database.

## Disposable database security

Each execution uses a disposable PostgreSQL instance in the same isolated execution Pod as the SQL runner. The trusted runner initializes the database using an execution-local owner credential and creates a constrained candidate login.

The candidate login is:

- `NOSUPERUSER`;
- `NOCREATEDB`;
- `NOCREATEROLE`;
- `NOINHERIT`;
- `NOREPLICATION`;
- `NOBYPASSRLS`;
- limited to the disposable execution database/schema objects required by the problem.

Credentials are generated for the execution and stored only in the short-lived Kubernetes execution Secret. They are not sent through SQS or persisted in application PostgreSQL.

## Query enforcement

Safety relies on disposable-database privileges, gVisor/container isolation, network isolation, credentials isolation, resource limits, and timeouts rather than SQL keyword parsing.

The candidate query is executed using PostgreSQL prepared/extended query execution, which also rejects multi-command submissions for the interview query surface.

Server-owned timeout layers include PostgreSQL `statement_timeout`, `lock_timeout`, `idle_in_transaction_session_timeout`, Kubernetes `activeDeadlineSeconds`, CPU, memory, and ephemeral-storage limits.

## Result protocol

The SQL runner emits the same versioned execution result protocol as Python, bound to execution ID and attempt. It returns column names and actual rows only. The trusted evaluator loads expected answers separately.

`sql_ordered` requires exact column order and row order. `sql_unordered` requires exact column order while treating row order as irrelevant; duplicates remain significant. `NULL`, numbers, text, timestamps, JSON-safe values, duplicate rows, and empty result sets are normalized deterministically.

Hidden expected rows are never included in the public execution projection.

## Remaining staging acceptance

Before SQL execution can be classified `STAGING VALIDATED`, a real AWS staging execution must prove:

1. SQS delivery to the trusted controller;
2. EKS scheduling onto the untrusted execution node group;
3. live `runsc`/gVisor runtime evidence;
4. disposable PostgreSQL lifecycle and cleanup;
5. denial of application RDS, Valkey, API, Kubernetes API, IMDS, Internet, and other sandbox access;
6. statement/resource timeout behavior;
7. cancellation, duplicate delivery, controller restart, lease expiry, and orphan cleanup.
