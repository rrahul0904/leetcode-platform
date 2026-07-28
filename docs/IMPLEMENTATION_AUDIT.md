# Implementation Audit

Audit date: 2026-07-28

## Executive conclusion

Rigor is a working Dockerized content and catalog foundation, but it is not yet a
reproducible candidate practice MVP. The live Docker volume is ahead of GitHub
`main`: it contains schema revision `20260721_0007`, 50 hosted questions, and 30
published questions, while `main` contains migrations only through
`20260720_0005` and four hosted question packages.

The immediate implementation target is therefore:

```text
published Python question
→ practice session and autosave
→ public-test run
→ idempotent final submission
→ hidden-test-safe deterministic evaluation
→ immutable competency evidence
→ readiness/confidence update
→ explainable next action
```

Simulation, AI interviewing, AWS infrastructure, and additional content breadth
remain secondary until this loop passes from fresh Docker volumes.

## Repository and branch state

Remote:

```text
https://github.com/rrahul0904/leetcode-platform.git
```

| Branch | HEAD | Remote state | Worktree state |
| --- | --- | --- | --- |
| `main` | `083544a` | pushed as `origin/main` | clean |
| `agent-1-platform-core` | `fc38d4c` | pushed | clean |
| `agent-2-practice-execution` | `d8788c7` | local only | modified `execution.py`; untracked `execution_sql.py` |
| `agent-3-simulation-interviews` | `083544a` | local only | substantial uncommitted API, UI, tests, and editor package |
| `agent-4-ai-personalization` | `fc38d4c` | local only | clean; no Agent 4 implementation |
| `agent-5-content-release` | `1da311c` | local only | committed 50-question release plus uncommitted catalog changes |

Branch ancestry is linear from `main`: Agent 1 is two commits ahead and Agent 5
is three commits ahead. Agent 2 contains the early Agent 1 contract checkpoint.
Agent 3 is based directly on `main`.

## Current architecture

### Runtime

- Next.js App Router candidate/admin web application.
- FastAPI modular monolith.
- PostgreSQL 18 with pgvector as system of record.
- Valkey for ephemeral state.
- Local OIDC provider for Docker development.
- Docker Compose one-shot services for migrations, seeding, source collection,
  content synchronization, and publication.
- Version-controlled hosted question packages and a separate external-reference
  catalog.
- FastAPI OpenAPI as the generated TypeScript contract source.

### Trust boundaries

- Authentication determines the candidate principal; clients must not supply
  candidate identity.
- Agent 1 adds transaction-local principal context and forced PostgreSQL RLS.
- Candidate code must run through an execution adapter, never inside FastAPI.
- Local execution is explicitly `LOCAL_FUNCTIONAL`, not a production security
  sandbox.
- Future production execution is designed for isolated gVisor-backed Kubernetes
  Jobs; it is not part of this MVP.
- External AI providers must remain behind a consent-aware provider-independent
  gateway and cannot determine correctness.

## Feature completion matrix

| Area | State | Evidence / gap |
| --- | --- | --- |
| Docker web/API/PostgreSQL/Valkey | Implemented on `main` | Services are healthy at ports 3001/8002/5434/6381 |
| Local OIDC and role-aware shell | Implemented | Candidate, reviewer, author, and administrator roles exist |
| External source registry | Implemented | Live DB contains 2,534 references and 17 sources |
| External competency mappings | Implemented | Existing release reports 5,990 mappings |
| Hosted content ingestion/review/publication | Implemented foundation | Main has four packages; Agent 5 has 50 |
| Published catalog API/UI | Implemented foundation | Candidate-safe list/detail routes exist |
| PostgreSQL roles and RLS | Complete on Agent 1 branch | Not merged to `main` |
| Shared practice/execution/evidence schema | Complete on Agent 1 branch | API repositories and candidate workflows are missing |
| Python functional execution | Partial | Baseline runner exists; hardened Agent 2 version is uncommitted |
| Disposable SQL sandbox | Partial | Agent 2 adapter exists as an untracked file; no integrated candidate path |
| Practice session API | Missing | No candidate create/autosave/state-transition router |
| Run API | Missing | No candidate question run route |
| Submission API/history | Missing | Table exists, but no integrated candidate route/repository |
| Deterministic submission evaluation | Missing | Basic test projection exists; no persisted evaluation domain |
| Competency evidence generation | Missing | Agent 1 table exists; no submission-to-evidence service |
| Readiness/confidence API | Missing | Agent 1 storage/contracts exist; no evidence aggregation API |
| Next-best-action engine | Missing | No explainable recommendation service |
| Candidate dashboard | Static/partial | Does not derive its primary state from real candidate evidence |
| System-design simulation | Substantial local partial work | Uncommitted and unregistered |
| Mock interviews | Substantial local partial work | Uncommitted and unregistered |
| AI gateway/interviewer | Missing | Contracts only |
| Learning plan personalization | Missing | Storage contracts only |
| Browser E2E candidate loop | Missing | Release blocker |
| CI | Missing | No `.github` workflow is present |

## Routes and information architecture

Candidate and administrative navigation are role-separated, but the candidate
navigation currently exposes unfinished surfaces:

```text
Home
Question bank
External practice
Learning paths
Mock interviews
Progress
```

Until they have real APIs, persistence, errors, empty states, tests, and a Docker
path, unfinished routes must be removed or gated. The target candidate navigation
is:

```text
Home
Practice
Interviews
Progress
```

Source governance, rights, ingestion, duplicate detection, reviews, and
publication remain under `/admin`.

## Database and migration state

`main` contains:

```text
20260720_0001_content_foundation
20260720_0002_m1_identity_onboarding
20260720_0003_m1_submissions
20260720_0004_content_ingestion
20260720_0005_continuous_content_intelligence
```

Agent 1 adds:

```text
20260721_0006_platform_domain
20260721_0007_external_progress
```

The live Docker database reports `20260721_0007`, so it is ahead of the code on
`main`. This old-volume dependency must be eliminated before release.

Agent 1 has already verified:

- initialization from empty PostgreSQL 18;
- downgrade and re-upgrade;
- runtime ownership separation;
- cross-candidate and cross-organization RLS denial;
- spoofed maintenance-bypass denial;
- SQL sandbox denial of application schema access.

## Content state

`main` contains four complete Python packages.

Agent 5 commit `1da311c` contains 50 packages:

```text
20 Python
10 SQL
5 system design
4 distributed systems
3 data modeling
3 data architecture
2 ML system design
2 generative AI architecture
1 AI infrastructure
```

Difficulty allocation is 5 foundational, 10 intermediate, 18 advanced, 12
staff, and 5 principal. Schema validation passes for all 50 packages.

Known content blocker: aggregate pytest collection fails because executable
packages reuse the top-level filename `test_reference.py`. Reference tests need
unique import namespaces or isolated execution before the release branch is
accepted.

## Toolchain state

- `.nvmrc`: Node `24.18.0`
- root package engine: `>=24.18.0 <25`
- web Docker image: pinned Node `24.18.0`
- Python packages: `>=3.13,<3.14`
- API Docker image: pinned Python `3.13.5`
- package manager: pinned pnpm `11.10.0`

The current host is running Node 26, so local JavaScript commands emit an engine
warning even though tests pass. CI must use Node 24.

## Test status

Verified on clean `main` during this audit:

```text
API / Python:          23 passed
Web test files:         6 passed
Web tests:             10 passed
Frontend lint:          passed
TypeScript typecheck:   passed
Docker Compose config:  passed
```

Agent 1 separately reports:

```text
API suite:              22 passed, 1 environment-dependent skip
Platform integration:    3 passed
Ruff:                    passed
Pyright:                 passed
API client typecheck:    passed
Migration/RLS checks:    passed against real PostgreSQL 18
```

Not yet passing:

- aggregate 50-package reference tests;
- practice/submission/evidence/readiness integration tests;
- browser E2E;
- clean-volume 50-hosted/30-published bootstrap.

## Reusable implementation

- Preserve Agent 1 roles, RLS, domain tables, health checks, and shared
  contracts.
- Preserve the hardened Agent 2 local Python runner after focused review.
- Preserve the Agent 2 disposable PostgreSQL adapter for the later SQL
  milestone.
- Preserve Agent 5 packages and release allocation, but repair test namespaces
  and clean bootstrap.
- Preserve Agent 3 simulation models, cases, and architecture editor in its
  isolated worktree until the Python evidence loop is complete.
- Reuse TanStack Query and the current authentication provider.
- Keep FastAPI as the source of OpenAPI and regenerate TypeScript contracts.

## Known blockers and risks

1. Live database state masks clean-checkout failures.
2. Main lacks the verified Agent 1 migrations and RLS runtime.
3. Practice APIs, persistence repositories, and UI do not exist.
4. No persisted deterministic submission evaluation exists.
5. Evidence/readiness/next-action services do not exist.
6. Four feature branches are local-only; two contain critical uncommitted work.
7. Central router and navigation registration will require deliberate
   integration to avoid duplicate models and dead routes.
8. Content executable tests collide during aggregate collection.
9. CI and browser E2E are absent.
10. Local OIDC browser tokens can become stale when Docker volumes are reset.

## Implementation plan

1. Merge Agent 1 into `main` and rerun migration/RLS/API checks.
2. Add safe `make bootstrap`, `make reset-local`, and prerequisite validation.
3. Prove clean-volume migration, seed, content sync, publication, and health.
4. Complete Python practice-session repository, state machine, autosave, and
   candidate-owned APIs.
5. Integrate the hardened `LOCAL_FUNCTIONAL` Python execution backend.
6. Implement separate run and submit flows, persisted idempotency, immutable
   submission history, and hidden-test-safe projections.
7. Persist deterministic submission evaluations.
8. Generate versioned immutable competency evidence from successful and failed
   final submissions.
9. Implement readiness score/confidence aggregation and explainable next action.
10. Build the candidate practice workspace and evidence-driven dashboard.
11. Repair and integrate the 50-question release.
12. Add API, PostgreSQL security, frontend, and browser E2E tests.
13. Run the final acceptance sequence from fresh Docker volumes and push
    coherent commits to `main`.

