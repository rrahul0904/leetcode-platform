# Implementation Progress

Baseline ledger verified: 2026-07-21  
Hosted reconstruction update: 2026-10-07 (America/New_York)

This ledger reports executable behavior and evidence, not planned scope. The historical 1,350-item manifest remains a launch-foundation benchmark; the platform has no final question-count ceiling.

## Reconstruction status

The current reconstruction is explicitly targeting a hosted product. Browser storage is not an authoritative persistence layer. Durable candidate state belongs behind authenticated APIs and managed data services; browser state is limited to ephemeral presentation concerns.

| Area | Current reconstruction status | Evidence / boundary |
| --- | --- | --- |
| Web application | Implemented and CI-verified | Next.js lint, typecheck, tests, and production build pass on the reconstruction branch |
| API and schemas | Implemented; reconstruction checks active | FastAPI serving composition, durable execution routes, SaaS/tutor/mock-interview/AI-arena/knowledge surfaces, strict Pyright, PostgreSQL integration |
| Database migrations | Implemented and CI-verified | PostgreSQL 18 + pgvector migration cycle upgrades from empty state and verifies execution, knowledge, SaaS, tutor, mock-interview, PR-review, and AI-arena schemas |
| Hosted configuration boundary | Implemented | Staging/production fail closed on local execution adapters, local OIDC, loopback PostgreSQL/operational PostgreSQL/Valkey, missing hosted identity configuration, and missing durable execution queue for Kubernetes execution |
| Candidate execution control plane | Implemented in source; certification incomplete | Durable SQS/DLQ/KMS queue, trusted controller identity, immutable execution-image path and async execution contracts exist |
| Candidate hostile-code plane | Implemented in Terraform source; not yet provisioned/certified | Guarded production EKS execution VPC, hardened custom AMI requirement, private control endpoint by default, isolated execution database, gVisor/Packer source validation |
| AWS application/data plane | Implemented in Terraform source; not yet provisioned | Production VPC, ECS, managed PostgreSQL, Valkey, object storage, queues, secrets, WAF, DNS and CDN composition validates in CI |
| Environment topology | Reconciled | `dev`, `staging`, and `prod` are canonical; obsolete empty `development` and `production` placeholders were removed |
| Live production deployment | **Not yet evidenced** | No claim of an AWS apply, cloud resource inventory, production DNS cutover, production secrets, hosted smoke test, backup/restore drill, or hostile-runner adversarial certification is made here |

Terraform source validation is not deployment evidence. Production readiness advances only after reviewed plans, a real apply, immutable image/AMI receipts, hosted smoke/recovery tests, and security certification.

## Historical July baseline

The following July evidence is retained for traceability and must not be read as the current completion ceiling.

| Area | July status | Verified evidence |
| --- | --- | --- |
| Docker application | Working locally | Web, API, PostgreSQL 18 + pgvector, and Valkey were healthy in the local development fixture |
| Authentication and authorization | Working locally | Local OIDC with PKCE/JWKS, normalized principals, roles, API permissions, expiry tests, and candidate/admin denial tests |
| Onboarding/profile | Working locally | Persisted candidate profile API/UI with authorization |
| Review/publication | Working locally | Durable assignments, separation of duties, technical/editorial decisions, state transitions, idempotent publication, and audit events |
| Candidate catalog safety | Working locally | PostgreSQL catalog served only published public versions; leakage tests covered solutions, hidden tests, and interviewer-only fields |
| Universal ingestion | Working locally | JSON, JSONL, CSV metadata, and safe ZIP parsing; strict discriminated schemas; rights/provenance, duplicate, execution, rubric, difficulty, security, durable reports, retry, and rollback |
| Content factory | Working locally | Maximum 10 items, single-track by default, complete ingestion gates, durable provider/model/prompt/hash traces, dry run, generated-draft state, no auto-publication |
| Source intelligence | Working locally | 2,534 legal metadata references from 5 approved connectors; prohibited sources blocked, credentialed sources paused, source policy and evidence recorded |
| Competency ontology | Working locally | 28 seeded competencies, 5,990 external mappings, deterministic pattern mapping, current gap counts, and hosted-question mappings |
| Original hosted content | Review-gated | 4 complete Python packages; all remained awaiting independent review at the July checkpoint |

## Historical content facts

These counts are the 2026-07-21 checkpoint and require a fresh corpus reconciliation before being presented as current production counts.

| Record | July checkpoint count |
| --- | ---: |
| Launch-foundation planning briefs | 1,350 |
| Discovered source-registry records | 17 |
| Approved source connectors | 5 |
| Competencies | 28 |
| External competency mappings | 5,990 |
| Hosted question records | 4 |
| External question references | 2,534 |
| Published candidate questions | 0 |

The original Python, PostgreSQL SQL, and system-design packages in the ingestion acceptance suite prove the schema and pipeline, but test fixtures are not counted as production content. The platform must not claim the planned bank is complete or candidate-ready until the current corpus is independently reconciled and reviewed.

## Implemented operator surfaces

- `/admin/sources` plus discovered, approved, blocked, failures, syncs, and coverage views
- `/admin/content/import` and `/admin/content/imports`
- `/admin/content/factory`
- `/content-review`
- `./scripts/content` commands for validate, import, duplicate checks, solution execution, rights checks, PostgreSQL sync, reports, and rollback

## Remaining blockers to a standing candidate-ready hosted product

1. Reconcile the current production corpus, independently review publishable packages, and establish a non-zero reviewed/published launch catalog with evidence.
2. Provision and certify the isolated hostile-code execution plane: build the hardened runsc/containerd AMI, apply the guarded production EKS/network/database resources, deploy immutable execution images, and pass adversarial escape/network/resource-limit tests.
3. Provision the hosted application/data plane from reviewed Terraform using encrypted remote state and deployment roles; configure real secrets, identity, DNS/TLS, observability, backups and restore evidence.
4. Prove end-to-end hosted execution from authenticated web request -> durable API/database state -> queue/outbox -> isolated worker -> durable result -> candidate-owned read, including retries, cancellation, DLQ and recovery.
5. Complete browser E2E, accessibility, load, hosted backup/restore, clean migration-cycle, disaster-recovery and rollback certification against deployed environments.
6. Complete canonical family classification, meaningful-variation controls, production scheduling/reviewer operations, and expand approved/licensed source-backed catalog coverage.
7. Obtain written permission or approved API credentials before enabling Reddit, NeetCode, DataLemur, StrataScratch, Interview Query, or other paused sources. LeetCode and HackerRank automated collection remains blocked by policy.

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
terraform fmt -check -diff -recursive infra/terraform
terraform -chdir=infra/terraform/environments/dev init -backend=false -input=false
terraform -chdir=infra/terraform/environments/dev validate
terraform -chdir=infra/terraform/environments/prod init -backend=false -input=false
terraform -chdir=infra/terraform/environments/prod validate
docker compose up -d --build
docker compose ps
```
