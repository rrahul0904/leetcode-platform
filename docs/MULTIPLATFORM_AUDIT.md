# Rigor Multiplatform Audit

## Status

This document records the verified starting point and the implementation boundaries for the Web, iOS, and Android workstream.

## Existing architecture retained

- `apps/web`: Next.js candidate and administration application.
- `apps/api`: FastAPI application and canonical business API.
- `packages/api-client`: generated OpenAPI TypeScript schema package.
- `services`: execution and durable-worker security boundaries.
- `database`: Alembic migrations and controlled seed data.
- `infra`: local and production infrastructure definitions.
- PostgreSQL/pgvector remains canonical for candidate, content, evidence, readiness, practice, and submission state.
- Valkey remains non-canonical coordination/cache infrastructure.
- Existing OIDC, PKCE, normalized principals, roles, and permissions remain the identity authority.

## Verified repository capabilities

The current repository already contains:

- a working Next.js web application;
- a FastAPI modular-monolith API;
- local PostgreSQL/pgvector and Valkey;
- candidate profile persistence and authorization;
- candidate-safe published catalog boundaries;
- practice-session and submission APIs;
- an evidence-backed Python practice loop;
- local functional execution and a Kubernetes Job execution adapter contract;
- generated OpenAPI TypeScript types;
- content ingestion, provenance, rights, review, and publication controls.

These capabilities must be extended, not recreated.

## Multiplatform ownership matrix

| Capability | Canonical owner |
| --- | --- |
| Authentication authority | OIDC provider + FastAPI principal normalization |
| Authorization | FastAPI |
| Candidate profile | FastAPI + PostgreSQL |
| Questions and publication state | FastAPI + PostgreSQL |
| Practice sessions and drafts | FastAPI + PostgreSQL, with optional client cache |
| Submissions and evaluations | FastAPI + PostgreSQL |
| Evidence and readiness | FastAPI + PostgreSQL |
| Web presentation | Next.js |
| Native presentation | Expo / React Native |
| Production untrusted execution | Dedicated execution plane |

## Shared-code policy

Share only platform-independent code:

- generated API contracts;
- the API transport factory;
- domain types and validation;
- TanStack Query keys and platform-neutral hooks;
- design tokens;
- formatting and competency utilities;
- telemetry event definitions.

Keep platform-specific:

- Next.js routes and rendering;
- Expo Router screens;
- web and native navigation;
- DOM and React Native components;
- CSS and native style implementations;
- secure token storage and lifecycle integration;
- editor rendering.

## API client finding

Before this workstream, `@rigor/api-client` exported only the generated OpenAPI schema. This branch adds a fetch-injected, platform-neutral API client factory that does not depend on `window`, `document`, browser storage, Next.js, Node-only modules, or React Native APIs.

## Mobile implementation boundary

The native client must use Expo Router and the same FastAPI contracts as the web application. It must not:

- create a second backend;
- accept candidate identity from request bodies;
- store tokens in AsyncStorage;
- execute candidate code on device;
- include administration/content-publication capabilities;
- calculate canonical readiness independently.

## Dependency and lockfile requirement

The repository enforces `pnpm install --frozen-lockfile`. Creating `apps/mobile` and new workspace packages therefore requires generating and committing the matching `pnpm-lock.yaml` importers in the same verified change. A partial hand-written Expo dependency graph is not acceptable.

The native scaffold should be generated with the stable SDK selected explicitly by the repository implementation task and then validated with Expo Doctor, lint, typecheck, tests, and the root Turborepo commands.

## Production infrastructure dependency

The client/API integration may use the existing local functional adapter while under development. Production candidate execution is not part of the mobile application and must remain behind the execution API contract.

The production workstream must provide:

- ECS Fargate for Next.js, FastAPI, and trusted workers;
- RDS PostgreSQL/pgvector;
- ElastiCache Valkey;
- private S3 buckets;
- SQS execution dispatch with durable/idempotent state transitions;
- a dedicated Kubernetes execution plane using gVisor;
- ephemeral PostgreSQL for candidate SQL;
- deny-by-default sandbox networking;
- no application credentials in candidate pods.

## Implementation order

1. Platform-neutral API transport and error model.
2. Shared query keys, domain boundaries, and design tokens.
3. Generate Expo application and lockfile together.
4. Implement OIDC Authorization Code + PKCE using SecureStore.
5. Build candidate home, catalog, practice, progress, interview, and profile routes.
6. Integrate execution status streaming with polling fallback.
7. Add cross-client and offline/lifecycle tests.
8. Implement and validate AWS control-plane infrastructure.
9. Implement and validate the isolated execution plane.

## Current branch status

Implemented in the first slice:

- platform-neutral API client factory;
- normalized API errors;
- shared query-key package;
- shared semantic design-token package;
- this audit.

Not yet claimed complete:

- Expo application scaffold;
- native OIDC flow;
- native screens;
- lockfile regeneration;
- AWS resources;
- gVisor runtime verification;
- staging or production deployment.
