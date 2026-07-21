# Implementation Progress

Verified: 2026-07-20

This ledger reports executable behavior, not planned scope. The 1,350-item manifest is the launch-foundation benchmark; the platform has no final question-count ceiling.

## Verification summary

| Area | Status | Verified evidence |
| --- | --- | --- |
| Docker application | Working locally | Web, API, PostgreSQL 18 + pgvector, and Valkey are healthy; `http://localhost:3001` and `http://localhost:8002/livez` respond |
| Web application | Working locally | 25 production routes compile; lint and TypeScript pass; 5 component tests pass |
| API and schemas | Working locally | 20 backend/schema tests pass; Ruff and strict Pyright report zero errors |
| Database migrations | Working locally | Alembic is at the single head `20260720_0005` |
| Authentication and authorization | Working locally | Local OIDC with PKCE/JWKS, normalized principals, roles, API permissions, expiry tests, and candidate/admin denial tests |
| Onboarding/profile | Working locally | Persisted candidate profile API/UI with authorization |
| Review/publication | Working locally | Durable assignments, separation of duties, technical/editorial decisions, state transitions, idempotent publication, and audit events |
| Candidate catalog safety | Working locally | PostgreSQL catalog serves only published public versions; leakage tests cover solutions, hidden tests, and interviewer-only fields |
| Universal ingestion | Working locally | JSON, JSONL, CSV metadata, and safe ZIP parsing; strict discriminated schemas; rights/provenance, duplicate, execution, rubric, difficulty, security, durable reports, retry, and rollback |
| Content factory | Working locally | Maximum 10 items, single-track by default, complete ingestion gates, durable provider/model/prompt/hash traces, dry run, generated-draft state, no auto-publication |
| Source intelligence | Working locally | Extensible registry, unreviewed-by-default connectors, legal coverage levels, review enforcement, approved-only incremental sync, separate external references, and coverage dashboard |
| Competency ontology | Foundation complete | 28 seeded competencies and hosted/external coverage query; family, variation, gap, and freshness operations remain incomplete |
| Submission execution | Partial | Submission table and local controlled Python/PostgreSQL adapters exist; candidate submission API/UI and production-isolation runner are incomplete |
| AWS deployment | Not started | Local Docker configuration is portable; production AWS Terraform/Kubernetes, secrets, observability, and sandbox infrastructure are not implemented |

## Current content facts

| Record | Current count |
| --- | ---: |
| Launch-foundation planning briefs | 1,350 |
| Discovered source-registry records | 17 |
| Approved source connectors | 0 |
| Competencies | 28 |
| Hosted question records | 0 |
| External question references | 0 |
| Published candidate questions | 0 |

The original Python, PostgreSQL SQL, and system-design packages in the ingestion acceptance suite prove the schema and pipeline, but test fixtures are not counted as production content. The application therefore must not claim that the planned bank is complete or candidate-ready.

## Implemented operator surfaces

- `/admin/sources` plus discovered, approved, blocked, failures, syncs, and coverage views
- `/admin/content/import` and `/admin/content/imports`
- `/admin/content/factory`
- `/content-review`
- `./scripts/content` commands for validate, import, duplicate checks, solution execution, rights checks, PostgreSQL sync, reports, and rollback

## Remaining blockers to a standing candidate-ready product

1. Author and independently review the initial production question packages; current published count is zero.
2. Complete the candidate submission API/UI and replace the local functional runner with a production-grade isolated execution plane.
3. Implement canonical family classification, meaningful-variation controls, automatic coverage-gap briefs, and freshness workflows.
4. Add the remaining question-operations pages for families, variants, gaps, duplicates, licenses, provenance, and freshness.
5. Add browser E2E, accessibility, load, backup/restore, and clean migration-cycle automation.
6. Build AWS production infrastructure: managed PostgreSQL/pgvector, cache, object storage, queues/workflows, secret management, logging/metrics/tracing, WAF/rate limits, and isolated execution workers.
7. Review and approve source rights before any connector collects metadata or content. Unauthorized copying or scraping is intentionally not implemented.

## Verification commands

```bash
uv run pytest -q
uv run ruff check apps/api/src packages/question-schema/src scripts apps/api/tests packages/question-schema/tests tests
uv run pyright apps/api/src packages/question-schema/src scripts
pnpm --filter @rigor/web lint
pnpm --filter @rigor/web typecheck
pnpm --filter @rigor/web test
pnpm --filter @rigor/web build
uv run alembic current
docker compose up -d --build
docker compose ps
```
