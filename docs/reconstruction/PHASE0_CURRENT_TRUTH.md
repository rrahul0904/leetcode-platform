# Phase 0: Current Truth

Snapshot update: 2026-10-14 America/New_York. Repository `rrahul0904/leetcode-platform`; PR #51 branch `codex/skillforge-production-reconstruction-v2`; observed PR HEAD `79d330af225e3f8df99023545916c95fe28de1f8`; observed `main` `2e785369d97c387932931e1954b1b715183b5784`. Evidence IDs are in [REA_EVIDENCE_LEDGER.md](REA_EVIDENCE_LEDGER.md).

## Architecture map

| Plane | Current source | Authority / status |
|---|---|---|
| Experience | `apps/web` Next.js App Router; `vercel.json` defines web service and same-origin `/api/backend` routes. | Canonical V1 project observed as `skillforge-platform`; authenticated Preview landing and sign-in routes returned HTTP 200 on exact SHA `79d330a`. |
| API | `apps/api/src/rigor_api`, FastAPI modular monolith; `apps/api/vercel_main.py` is Vercel entrypoint. | The service-specific install fixed the missing FastAPI import on SHA `b1e31a1`; startup now fails because `/var/task/content/question-bank-manifest.json` is absent from the function bundle. Packaging that runtime file is the next repair. |
| Identity | Clerk values mapped into OIDC settings in `apps/api/src/rigor_api/config.py`; Next middleware in `apps/web/proxy.ts`. | Internal user/candidate row is durable identity; live auth path UNKNOWN. |
| Data | SQLAlchemy models and Alembic migrations in API; PostgreSQL RLS and runtime role migrations. | Application PostgreSQL/Neon is authoritative; production DB identity/version and live RLS evidence unavailable. |
| Execution | Durable requests/outbox/results; Vercel Sandbox adapter; separate SQS/EKS controller stack remains in Terraform. | Vercel Sandbox is V1 choice. Kubernetes has separate state/network and is now fail-closed in code. |
| AI | Server-side provider abstraction, tutor/interview/arena persistence. | No hidden evaluator material may enter AI context; deployed provider journey UNKNOWN. |
| Operations | OpenTelemetry foundations, Terraform, security and runbook docs. | Source/checks exist; no claim of production apply, backup restore, domain promotion or alert verification. |

## Feature inventory

Implemented source surfaces include question/content governance; Python and SQL practice; execution and attempts; candidate progress/readiness; learning plans; tutor; mock interviews and simulations; PR review; company/knowledge; AI Arena; code typing and typing arcade; subscription/entitlement models; admin/reviewer workflows. Presence in source is not production availability. See [CAPABILITY_MATRIX.md](CAPABILITY_MATRIX.md) for decisions and acceptance gates.

## Route, data, migration and environment inventories

- Candidate and operator UI routes observed under `apps/web/app`:
  - `/` (marketing/home), `/sign-in`, `/sign-up`, `/auth/callback`, `/onboarding`, `/profile`, `/settings/[[...settings]]`
  - `/question-bank`, `/question-bank/[slug]`, `/question-bank/[slug]/solution`, `/questions/[slug]`, `/questions/[slug]/solution`, `/problems`, `/problems/[slug]`, `/practice/[slug]`, `/coding-lab`, `/external-practice`
  - `/attempts`, `/progress`, `/learning-paths`, `/study-workspace`, `/workspace`, `/journal`, `/journal/[slug]`, `/resources`, `/foundation`
  - `/practice/code-typing`, `/practice/typing-arcade`, `/design-lab`, `/mock-interviews`, `/companies`, `/ai-arena`, `/pr-review`, `/system-design-library`, `/system-design-library/[slug]`
  - `/content-review`, `/reviewers`, `/quality-gates`; admin routes `/admin/catalog-status`, `/admin/content/factory`, `/admin/content/import`, `/admin/content/imports`, `/admin/questions`, `/admin/questions/{duplicates,families,freshness,gaps,library,licenses,new,provenance,variants}`, `/admin/sources`, `/admin/sources/{approved,blocked,discovered,failures,syncs}`
  - API proxy route `/api/backend/[...path]`; Clerk webhook route `/api/webhooks/clerk`.
- API route composition is in `apps/api/src/rigor_api/main.py`; modules include execution, candidate submission, knowledge/catalog/company/progress, content/review, identity/health, tutor, mock interview, PR review, SaaS, and AI Arena. Data contracts are in `schemas.py`; SQL access is primarily `persistence.py`, domain repositories and database modules. Core data families include users/roles/profiles/organizations; questions/versions/reviews/provenance; practice sessions/submissions/executions/results/evidence/readiness; learning plans; knowledge sources/problems/companies/topics/progress; tutor sessions/events; mock-interview/simulation sessions/reports; PR review sessions/comments; AI Arena profiles/generations/results/limits; subscriptions/entitlements; private files/deletion/export requests.
- Migration inventory is `database/migrations/versions`: `20260720_0001` content foundation; `20260720_0002` identity/onboarding; `20260720_0003` submissions; `20260720_0004` ingestion; `20260720_0005` content intelligence; `20260721_0006` platform domain; `20260721_0007` external progress; `20260728_0008` practice evidence; `20260728_0009` execution queue; `20260729_0010` async results; `20260729_0011` worker security; `20260801_0012` knowledge bank; `20260801_0013` knowledge progress; `20260801_0014` knowledge hardening; `20260802_0015` local execution queue; `20260824_0016` large corpus serving; `20260826_0017` SaaS foundation; `20260828_0018` question engagement; `20260911_0019` tutor sessions; `20260914_0020` PR review; `20260918_0021` AI Arena. `.venv/bin/alembic heads` reports `20260918_0021 (head)`. Production DB version remains UNKNOWN.
- Runtime setting names are documented in `.env.example`, `apps/api/src/rigor_api/config.py`, `vercel.json`, and Terraform maps. API settings include `RIGOR_ENVIRONMENT`, `RIGOR_DATABASE_URL`, `RIGOR_OPERATIONAL_DATABASE_URL`, `RIGOR_VALKEY_URL`, `RIGOR_EXECUTION_ADAPTER`, `RIGOR_AI_ADAPTER`, Clerk issuer/JWKS/webhook values, `RIGOR_JWT_AUDIENCE`, AWS region, SQS execution queue, S3 upload/export buckets, Sentry DSN, OpenAI key, and Arena generation limit. Vercel config selects Clerk, same-origin `/api/backend`, production environment and `VERCEL_SANDBOX`. Secret values are intentionally not collected.
- Database current content counts are UNKNOWN. Historical docs explicitly label their counts as dated baselines; they are not launch inventory evidence.

## Deployment topology and blockers

`skillforge-platform` is the canonical Preview project; `skillforge-reconstruction` is a separate reconstruction deployment and is not the release target. Vercel protection remains enabled. An authorized project-scoped Preview automation bypass is stored only in GitHub environment `Preview – skillforge-platform`; Production has no bypass secret. The exact-SHA deployment `GJaYTDQSnn5eCxiNhVEJiqumW5gH` (SHA `79d330a`) returned HTTP 200 for `/` and `/sign-in`, and HTTP 500 for `/api/backend/livez` and `/api/backend/readyz` because FastAPI was absent. The service-specific install then included FastAPI on SHA `b1e31a1`, but its API health probes still returned 500 because the function bundle lacks `content/question-bank-manifest.json`. The latest observed Production deployment remains on older SHA `7deda4195838941d7c14ecf7b1e09b58062c9cee`. Two P1 review findings concern Kubernetes requests without healthy workers and the disconnected controller database/VPC. Exact deployment and check evidence: REA-002 through REA-007 and the 2026-10-14 updates below.

Open blockers: hosted API import/readiness; live Clerk journey; live Neon/RLS/migration evidence; Vercel Sandbox Python/SQL execution and adversarial certification; current reviewed content inventory; completed security/accessibility/load/recovery checks; P1 review closure with exact-head evidence; production staging, smoke and exact-SHA receipt. Project status: **NOT YET CERTIFIED**.
