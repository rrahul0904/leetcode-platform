# Rigor multi-platform testing

## Layers

1. domain and generated-contract tests;
2. platform-neutral HTTP/query tests;
3. web component tests;
4. native component/workflow tests;
5. FastAPI/backend tests;
6. integration tests against local Docker;
7. cross-client E2E;
8. staging execution-isolation tests.

## Native acceptance scenarios

- signed-out bootstrap routes to sign-in;
- Authorization Code + PKCE returns a candidate principal;
- non-candidate principal cannot enter candidate tabs;
- published catalog loads without hidden content;
- question opens by deep-link-compatible slug;
- practice session is created on the shared backend;
- code draft persists on-device and synchronizes to server;
- newer unsynced local draft is not silently overwritten by older server data;
- Run renders public-test results only;
- Submit sends an idempotency key and renders persisted evaluation;
- readiness/progress refetch after confirmed submission;
- offline/API error state preserves draft;
- expired authentication clears the secure session safely.

## Cross-client scenarios

After durable APIs exist for the domain, prove:

- web-created practice session visible on native;
- native submission visible on web;
- profile changes converge through FastAPI/PostgreSQL;
- readiness/evidence values match across clients;
- durable interview history matches across clients.

## Production execution scenarios

Before compute enablement in staging, prove timeout, output/process/memory/disk limits, network denial, metadata denial, no RDS/Valkey access, sandbox-to-sandbox denial, duplicate SQS safety, cancellation, orphan reconciliation, and cleanup TTL.

## PR gate

`.github/workflows/pr-validation.yml` refreshes the same-repository branch lockfile/formatting and then runs frozen dependency install, JS checks, backend checks, Alembic-head verification, Terraform validation, and production Docker image builds.
