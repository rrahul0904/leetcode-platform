# ADR-004: Authoritative Application and Execution State

- Status: Accepted for V1
- Date: 2026-10-13

## Decision

Managed PostgreSQL/Neon is the authoritative application database for identity mapping, candidate-owned state, durable execution requests/results, attempts and readiness evidence. A secondary database may not silently become an execution authority. Browser storage is ephemeral presentation or a temporary draft with eventual server synchronization.

## Consequences

Execution providers receive only the data necessary to run immutable source and fixtures. Workers must reconcile durable state and idempotency through the authoritative path. Any future separate operational store needs an explicit data ownership and recovery contract; it cannot own execution status by implication.
