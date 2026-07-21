# Implementation Progress

Verified: 2026-07-21

This ledger reports executable behavior, not planned scope. The 1,350-item manifest is the launch-foundation benchmark; the platform has no final question-count ceiling.

## Verification summary

| Area | Status | Verified evidence |
| --- | --- | --- |
| Docker application | Working locally | Web, API, PostgreSQL 18 + pgvector, and Valkey are healthy; `http://localhost:3001` and `http://localhost:8002/livez` respond |
| Web application | Working locally | 35 production routes compile; lint and TypeScript pass; 9 component tests pass |
| API and schemas | Working locally | 23 backend/schema tests pass; Ruff and strict Pyright report zero errors |
| Database migrations | Working locally | Alembic is at the single head `20260720_0005` |
| Authentication and authorization | Working locally | Local OIDC with PKCE/JWKS, normalized principals, roles, API permissions, expiry tests, and candidate/admin denial tests |
| Onboarding/profile | Working locally | Persisted candidate profile API/UI with authorization |
| Review/publication | Working locally | Durable assignments, separation of duties, technical/editorial decisions, state transitions, idempotent publication, and audit events |
| Candidate catalog safety | Working locally | PostgreSQL catalog serves only published public versions; leakage tests cover solutions, hidden tests, and interviewer-only fields |
| Universal ingestion | Working locally | JSON, JSONL, CSV metadata, and safe ZIP parsing; strict discriminated schemas; rights/provenance, duplicate, execution, rubric, difficulty, security, durable reports, retry, and rollback |
| Content factory | Working locally | Maximum 10 items, single-track by default, complete ingestion gates, durable provider/model/prompt/hash traces, dry run, generated-draft state, no auto-publication |
| Source intelligence | Working locally | 2,534 legal metadata references from 5 approved connectors; prohibited sources blocked, credentialed sources paused, source policy and evidence recorded |
| Competency ontology | Working locally | 28 seeded competencies, 5,990 external mappings, deterministic pattern mapping, current gap counts, and hosted-question mappings |
| Original hosted content | Review-gated | 4 complete Python packages; 3 were selected from measured data-architecture, observability, AI-evaluation, and experimentation gaps; all remain awaiting independent review |
| Submission execution | Partial | Submission table and local controlled Python/PostgreSQL adapters exist; candidate submission API/UI and production-isolation runner are incomplete |
| AWS deployment | Not started | Local Docker configuration is portable; production AWS Terraform/Kubernetes, secrets, observability, and sandbox infrastructure are not implemented |

## Current content facts

| Record | Current count |
| --- | ---: |
| Launch-foundation planning briefs | 1,350 |
| Discovered source-registry records | 17 |
| Approved source connectors | 5 |
| Competencies | 28 |
| External competency mappings | 5,990 |
| Hosted question records | 4 |
| External question references | 2,534 |
| Published candidate questions | 0 |

The original Python, PostgreSQL SQL, and system-design packages in the ingestion acceptance suite prove the schema and pipeline, but test fixtures are not counted as production content. The application therefore must not claim that the planned bank is complete or candidate-ready.

## Implemented operator surfaces

- `/admin/sources` plus discovered, approved, blocked, failures, syncs, and coverage views
- `/admin/content/import` and `/admin/content/imports`
- `/admin/content/factory`
- `/content-review`
- `./scripts/content` commands for validate, import, duplicate checks, solution execution, rights checks, PostgreSQL sync, reports, and rollback

## Remaining blockers to a standing candidate-ready product

1. Independently technically and editorially review the four initial production packages; current published count is zero.
2. Complete the candidate submission API/UI and replace the local functional runner with a production-grade isolated execution plane.
3. Implement canonical family classification and meaningful-variation controls; coverage briefs and freshness inventory exist but require production scheduling and reviewer operations.
4. Expand the source-backed catalog with additional approved/licensed adapters and improve topic-to-competency calibration.
5. Add browser E2E, accessibility, load, backup/restore, and clean migration-cycle automation.
6. Build AWS production infrastructure: managed PostgreSQL/pgvector, cache, object storage, queues/workflows, secret management, logging/metrics/tracing, WAF/rate limits, and isolated execution workers.
7. Obtain written permission or approved API credentials before enabling Reddit, NeetCode, DataLemur, StrataScratch, Interview Query, or other paused sources. LeetCode and HackerRank automated collection remains blocked by policy.

## Verification commands

```bash
uv run pytest -q
uv run ruff check apps/api/src packages/question-schema/src scripts apps/api/tests packages/question-schema/tests tests
uv run pyright apps/api/src packages/question-schema/src scripts
SSL_CERT_FILE="$PWD/.docker-build-ca.pem" ./scripts/collect-external-references --ca-file "$PWD/.docker-build-ca.pem"
pnpm --filter @rigor/web lint
pnpm --filter @rigor/web typecheck
pnpm --filter @rigor/web test
pnpm --filter @rigor/web build
uv run alembic current
docker compose up -d --build
docker compose ps
```
