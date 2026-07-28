# Rigor mobile architecture

## Goal

The native client is a candidate-focused Expo/React Native application that uses the same FastAPI identity, profile, catalog, practice, submission, evidence, readiness, and history contracts as the web application.

It is not a WebView wrapper and does not own canonical candidate business state.

## Navigation

Primary tabs:

- Home
- Practice
- Interviews
- Progress
- Profile

Admin/source/rights/ingestion/publication operations remain web-only.

## Shared layers

- `@rigor/api-client`: generated OpenAPI schema plus platform-neutral HTTP transport.
- `@rigor/query`: stable cross-client query keys.
- `@rigor/design-tokens`: semantic visual tokens.

Native UI, navigation, lifecycle, local storage, and authentication persistence stay platform-specific.

## Authentication

Authorization Code + PKCE opens in the system browser. Tokens are persisted with Expo SecureStore. Candidate identity/organization/roles are derived by FastAPI from the validated principal; no request body can choose candidate identity.

## Connectivity

TanStack Query is connected to React Native foreground/background state and Expo Network online state. Queries can refetch after reconnect/foreground. Mutations do not automatically retry, which avoids accidental duplicate submissions.

## Practice

Phone layouts use Problem / Editor / Results panes. Tablets can render problem and editor/results side-by-side.

Practice sessions and confirmed submissions are canonical server state. SQLite stores local code drafts so navigation, process restart, or transient loss of network does not erase work. Device drafts record local and last-known server timestamps; a newer local draft can be restored rather than silently overwritten by an older server copy.

Run and Submit remain distinct. Run evaluates visible tests. Submit sends an idempotency key and produces persistent evaluation/evidence only after backend confirmation.

## Interviews

The native Interviews tab intentionally does not create local canonical interview records. The existing web mock-interview timer is not yet a durable backend domain. Native history will be implemented only after FastAPI owns interview sessions and feedback.

## Production execution

The mobile app never executes candidate Python/SQL for grading. It sends source to FastAPI; production FastAPI will enqueue execution and clients observe backend canonical state. Production sandbox implementation is tracked separately in the execution infrastructure work.
