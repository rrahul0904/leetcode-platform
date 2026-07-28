# Rigor multi-platform audit

Verified against repository baseline `2e45d43b09ac98d9c184923d4d84182ba4d36f89` before this branch was created.

## Existing architecture reused

- `apps/web`: Next.js App Router candidate/admin application.
- `apps/api`: FastAPI modular monolith and API source of truth.
- PostgreSQL + pgvector canonical state with Alembic migrations and candidate RLS.
- Valkey local cache/coordination service.
- Generated TypeScript OpenAPI schema in `packages/api-client`.
- Local OIDC provider with PKCE/JWKS, normalized principals, candidate/admin roles, and authorization tests.
- Candidate profile, published candidate-safe catalog, practice sessions, submissions, deterministic evaluation, evidence, readiness, and next-action APIs.
- Existing content, rights, source-intelligence, review/publication, and ingestion workflows.
- Existing execution adapters: local functional Python, disposable PostgreSQL SQL, and a Kubernetes Job contract for gVisor isolation.

## Important baseline limits

- Candidate submission execution is still synchronous/inline in the FastAPI request path.
- The local functional Python adapter explicitly is not a production security sandbox.
- The Kubernetes adapter is a contract/foundation; a production AWS execution cluster and validated runsc nodes were not present.
- AWS deployment had not been implemented.
- Web API transport was browser-specific and mobile did not exist.
- Web mock interviews were local timer state, not durable cross-device interview records.

## Shared ownership model

| Capability | Canonical owner |
| --- | --- |
| Identity principal | OIDC + FastAPI normalization |
| Authorization | FastAPI |
| Candidate profile | PostgreSQL/FastAPI |
| Questions | PostgreSQL/FastAPI |
| Practice session | PostgreSQL/FastAPI |
| Submission | PostgreSQL/FastAPI |
| Evaluation/evidence/readiness | PostgreSQL/FastAPI |
| Web rendering | Next.js |
| Native rendering | Expo/React Native |
| Local mobile code draft | SQLite, synchronized to practice session |
| Production code execution | isolated execution plane |

No native table or client model is allowed to become a second canonical candidate system.

## Shared package policy

This branch adds or extends platform-independent packages for:

- HTTP transport and generated OpenAPI contracts;
- query keys;
- semantic design tokens.

UI remains platform-specific. React Native does not import browser CSS or Next.js components.

## Authentication architecture

Web keeps the existing browser OIDC/session integration while the native app adds Authorization Code + PKCE through the system browser. Native access/refresh tokens are held in Expo SecureStore, not AsyncStorage.

The native app accepts candidate principals only; admin/content operations remain web-only.

## Practice architecture

Phone practice uses separate Problem / Editor / Results panes. Tablet layouts use a split problem/editor/results arrangement. Draft source is written locally before network synchronization, and submit mutations use idempotency keys and are never automatically retried.

Run remains temporary. Submit remains the evidence-producing persisted attempt.

## Production dependency

The multi-client layer can use the existing local execution adapter for local development. Production enablement is blocked until the infrastructure prompt's queued execution path replaces inline execution. See `docs/IMPLEMENTATION_NOTES_MULTICLIENT_INFRA.md`.
