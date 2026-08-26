# SkillForge / Rigor — Next Milestone Multi-Agent Execution Prompt

## Mission

Act as a coordinated team of senior data-platform, product, execution-sandbox, frontend, backend, AI, SRE, and release engineers working on `rrahul0904/leetcode-platform`.

The next milestone is **not another UI redesign**. The milestone is complete only when a real user can execute this flow against the real serving corpus:

> Open SkillForge → search the real large question corpus → filter it → open any published runnable question → solve it → Run → Submit → receive validated results → persist the attempt/progress → reload and recover the state.

The supplied project progress says the product has a strong interactive prototype and substantial application foundation, but the real large-corpus serving layer, complete persistence, durable production execution, and full end-to-end validation are not yet closed. It also reports audited 100K and 1M source banks that are source-ready but not yet serving through the application.

Repository verification shows the codebase has advanced further in several areas:

- PR #5 merged a durable local Docker application with PostgreSQL-backed execution queue and isolated Python/SQL runner services.
- PR #6 contains browser E2E, resilience, observability, and capacity evidence work.
- PR #7 implements source-backed question-bank release gates and a five-agent fail-closed release coordinator. Those gates are intentionally BLOCKED where exact source, rights, governance, or Run→Submit evidence is absent.
- PR #8 contains a reusable coding pad and explicitly states that the next work is wiring published questions to real Run/Submit and adding question-bank status filtering.

Therefore: **do not rebuild existing execution foundations, do not weaken provenance/rights gates, and do not spend this milestone on cosmetic expansion.**

---

# Non-Negotiable Engineering Rules

1. **Inspect the repository before coding.** Do not implement based only on this prompt.
2. **Preserve all existing release gates.** Never fabricate missing source provenance, publication rights, governance approval, or execution evidence.
3. **The 1M source-bank claim is not equivalent to 1M served questions.** Physical source artifacts, manifests, imports, database counts, publication state, and serving counts must be measured separately.
4. **No count may be claimed from targets or extrapolation.** Report physical file/database/API counts only.
5. **Raw archives/Parquet are import inputs, not runtime serving stores.** The web application must query a normalized database/API layer.
6. **Imported does not mean published.** Preserve publication status, rights status, provenance, and runnable/reference-only/review states.
7. **Candidate code never executes in the web/API process.** Reuse the existing durable execution contract and isolated runner boundaries.
8. **Run and Submit must be idempotent.** Duplicate delivery cannot create duplicate effects or duplicate attempts.
9. **Fail closed on missing security, provenance, rights, runtime package, hidden-test, or tenant/candidate authorization evidence.**
10. **No agent may silently change another agent’s contract.** Interface changes require the Integration Agent to approve and document them.
11. **Every PR must be independently testable and small enough to review.**
12. **Do not merge to `main` until the end-to-end milestone gate passes on the aggregate head.**

---

# Base and Integration Strategy

Current integration base for this wave:

`agent/question-bank-coding-pad`

Create all workstream branches from the integration branch once contracts are frozen. Do not branch independently from stale `main` and then force-merge unrelated histories.

Target branch for this orchestration wave:

`agent/next-milestone-multi-agent`

The Integration Agent owns only contracts, shared migration ordering, merge sequencing, conflict resolution, and aggregate release evidence. It should not absorb feature work that belongs to specialist agents.

---

# Milestone Definition of Done

The milestone is PASS only if all of the following are demonstrated on one aggregate commit:

## Corpus / Database

- The available audited large corpus is physically located and its manifest/checksums are verified.
- A documented importer supports large Parquet/JSONL ingestion in bounded batches.
- Import is restartable and idempotent.
- Staging → normalization → validation → publication-state classification is implemented.
- Canonical/reference/variant/review/runnable state is represented explicitly.
- Import reconciliation reports actual source rows, accepted rows, rejected rows, duplicate IDs/fingerprints, published rows, runnable rows, and reference-only rows.
- Re-running an already completed batch does not duplicate questions or associations.

## Search / Question Bank

- Question Bank is database-backed, not demo-array-backed.
- Server-side pagination works at large corpus scale.
- Filters work for platform/topic/subtopic/difficulty/seniority/company/industry/status where the data exists.
- Full-text search is real.
- Semantic/hybrid search uses embeddings only where actual embedding coverage exists; missing embeddings must not be represented as complete.
- Search results expose publication/runnable/reference/review state clearly.
- Arbitrary question detail routes resolve from the database.

## Question Detail

Each published question route provides the applicable subset of:

- Problem
- Constraints
- Schema/input/example data
- Starter code
- Solution/explanation subject to publication rules
- AI Tutor entry point only if retrieval context is trustworthy
- Similar questions
- Bookmarks/notes
- Attempt history
- Runnable status

## Python / SQL Run + Submit

For a published runnable question:

- Run executes public tests through the existing durable execution API.
- Submit executes public + hidden tests through the trusted evaluator.
- Candidate does not receive hidden test inputs/expected outputs.
- SQL uses isolated execution data, not application PostgreSQL.
- Python and SQL enforce time/resource boundaries already defined by the execution plane.
- duplicate Run is idempotent;
- duplicate Submit is idempotent;
- refresh/reconnect can recover terminal result state.
- cancellation and failure states remain consistent with the durable state machine.

## Persistence

- Attempts persist in PostgreSQL/Supabase only according to the actual repository architecture; do not assume an outdated design.
- Bookmark/note/draft persistence is real for authenticated users.
- Progress is derived from actual attempt events.
- User-scoped authorization/RLS tests prevent cross-user reads/writes.
- Refreshing the browser preserves the latest relevant state.

## E2E

A browser test must prove:

1. authenticate;
2. open Question Bank;
3. search a database-backed corpus term;
4. apply at least one server-side filter;
5. open a published runnable Python question;
6. edit code;
7. Run and observe public-test result;
8. Submit and observe hidden-test-backed result;
9. reload and recover persisted attempt/result;
10. repeat for SQL;
11. verify a reference-only question cannot execute;
12. verify one authorization boundary;
13. verify accessible keyboard interaction on the critical path.

## Release Evidence

Aggregate gate must include:

- Python lint/types/tests;
- Web lint/types/tests/build;
- migration upgrade and idempotency checks;
- import reconciliation;
- search API tests;
- Python/SQL runner tests;
- authorization/RLS tests;
- browser E2E;
- accessibility checks on the critical path;
- execution image/security checks already required by repository policy;
- backup/restore sanity for newly persisted data;
- no regression or bypass of source-bank release agents.

---

# Agent 0 — Integration Architect / Release Conductor

## Ownership

Own the contracts and aggregate branch, not feature implementation.

## Tasks

1. Inspect PRs #7 and #8 and the repository’s current schema/API contracts.
2. Publish a short `NEXT_MILESTONE_CONTRACT.md` defining:
   - question publication states;
   - runnable/reference/review semantics;
   - importer batch contract;
   - question-search API contract;
   - question-detail API contract;
   - Run/Submit request/result contract references;
   - attempt/progress event contract;
   - Scenario/Question ID and provenance invariants.
3. Freeze migration numbering/ranges so parallel agents do not collide.
4. Maintain a dependency matrix and merge order.
5. Review every agent PR for contract drift.
6. Run aggregate release gates after each integration wave.

## Must Not Do

- invent missing rights/provenance evidence;
- repin immutable reviewed hashes;
- weaken publication gates;
- rewrite specialist features unless necessary to resolve an integration defect.

---

# Agent 1 — 1M Corpus Ingestion & Canonicalization

## Objective

Turn the available audited large corpus into a trustworthy database import path.

## Required Work

- Locate the actual 100K/1M artifacts and manifests available to the project. If unavailable in the repository/runtime, report BLOCKED rather than generating replacement rows.
- Validate schema, required fields, row counts, IDs, fingerprints, and checksums.
- Implement bounded Parquet/JSONL reader(s).
- Create staging tables or equivalent safe staging path.
- Normalize the available 28-field source contract into the canonical question schema without dropping provenance.
- Preserve source file, source row, batch ID, import ID, fingerprint, version, license/rights state, and publication state.
- Add deterministic classification for at least:
  - canonical/publishable candidate;
  - legitimate variant;
  - near-concept duplicate/review;
  - reference-only;
  - runnable candidate;
  - rejected/quarantine.
- Implement restart checkpoints and repeat-import idempotency.
- Produce a machine-readable reconciliation report.

## Acceptance Tests

- fixed test corpus imports twice with no duplicate effects;
- deliberately malformed records are rejected with reason codes;
- duplicate ID/fingerprint handling is deterministic;
- process does not require loading the whole corpus into memory;
- large-batch benchmark reports throughput and memory behavior;
- actual source counts and database counts are reported separately.

## Deliverable

One focused PR plus import operator documentation.

---

# Agent 2 — Database-Backed Search & Question Serving

## Objective

Replace representative/demo question browsing with the actual serving database.

## Required Work

- Implement/finish server-side search, filtering, sorting, and cursor/page pagination.
- Support status-aware filtering: runnable, published/reference, review/quarantine where appropriate.
- Add stable arbitrary question-detail route lookup by canonical ID/slug.
- Ensure search facets derive from database values, not hardcoded arrays.
- Add full-text indexes and query plans appropriate for scale.
- Use pgvector/hybrid search only against actual embedded rows; expose embedding coverage honestly.
- Add search observability: p50/p95 latency, result count, query type, filter cardinality, zero-result rate.

## Acceptance Tests

- database-backed fixtures only;
- pagination does not duplicate or skip rows under a stable sort;
- status filters cannot leak quarantined/unpublished content to normal candidates;
- explain/query-plan evidence for representative large-table search;
- API returns deterministic empty states and invalid-filter behavior.

## Deliverable

One focused PR with API and web wiring for the Question Bank.

---

# Agent 3 — Question Detail Experience & User Persistence

## Objective

Make every served question a durable product object rather than a transient demo card.

## Required Work

- Arbitrary `/questions/<id-or-slug>` route backed by real API/database data.
- Preserve publication and runnable state in the UI.
- Real bookmarks, notes, drafts, attempt history, and recent-question state.
- Use existing auth model and user-scoped database policies.
- Remove remaining local/demo state where server persistence is required.
- Keep local draft recovery only as a resilience layer, not the system of record for attempts.
- Expose solution/explanation only when publication rules allow it.

## Acceptance Tests

- reload recovers user state;
- one user cannot read/write another user’s bookmark/note/attempt;
- unpublished/review content cannot be reached through guessed URLs;
- reference-only question clearly disables Run/Submit;
- route handles missing/deprecated IDs predictably.

## Deliverable

One focused PR.

---

# Agent 4 — Python + SQL Judge Integration

## Objective

Wire the existing coding pad to the existing durable execution plane for genuinely published runnable questions.

## Required Work

- Reuse the current asynchronous Run/Submit/Status/Cancel contract.
- Map question runtime package → starter code → public tests → hidden tests → trusted evaluator.
- Do not execute candidate code inside Next.js/FastAPI application workers.
- Python runner: enforce existing CPU/time/memory/process/network/filesystem restrictions.
- SQL runner: create/use per-question disposable schema/fixtures in isolated SQL execution database.
- Ensure hidden tests/expected results are not serialized to candidate clients.
- Add duplicate Run/Submit idempotency verification.
- Add result recovery after browser refresh or temporary network interruption.
- Preserve cancellation and retry semantics.

## Acceptance Tests

- one real published Python package passes and fails correctly;
- one real published SQL package passes and fails correctly;
- public tests visible, hidden tests protected;
- duplicate Run/Submit has one business effect;
- reference-only question cannot create an execution job;
- cross-user execution result lookup is denied;
- runner images/security checks remain green.

## Deliverable

One focused PR.

---

# Agent 5 — Attempts, Progress & Readiness Foundation

## Objective

Persist the evidence produced by real practice without inventing mastery intelligence yet.

## Required Work

- Append-only attempt/activity event path for Run/Submit/solve/fail/cancel where existing design permits.
- Derive latest attempt and basic topic/subtopic counters from real events.
- Persist time spent and language where reliable.
- Expose a deterministic minimal progress projection.
- Do **not** invent adaptive scoring/readiness formulas in this wave unless they already exist and can be verified.
- Keep the model extensible for later mastery/readiness work.

## Acceptance Tests

- submitting a question creates exactly one logical attempt outcome;
- duplicate delivery does not double-count progress;
- topic progress is reproducible from event history;
- user scoping is enforced;
- backup/restore retains progress evidence.

## Deliverable

One focused PR.

---

# Agent 6 — End-to-End Verification / SRE / Release Gate

## Objective

Prove the milestone as a user-visible system rather than trusting unit tests from individual agents.

## Required Work

- Build Playwright E2E for search → open → edit → Run → Submit → persist/recover.
- Cover Python and SQL.
- Cover reference-only non-executable state.
- Cover one authorization/RLS boundary.
- Cover keyboard/accessibility on critical flow.
- Add import/search/execution/persistence metrics needed to debug failed E2E.
- Run controlled volume test on search and the execution queue.
- Verify backup/restore with the new persisted entities.
- Produce `NEXT_MILESTONE_RELEASE_REPORT.md` with literal commit SHA and physical counts.

## Gate Rule

This agent cannot mark PASS if any prior agent reports missing physical corpus artifacts, missing publication rights, missing executable runtime packages, or unverified hidden tests. Report BLOCKED accurately.

---

# Parallel Execution Waves

## Wave 0 — Contract Freeze

Only Agent 0 executes repository-wide contract work.

Outputs required before parallel merges:

- state model;
- migration ownership;
- API contract;
- ID/provenance rules;
- branch/merge order.

## Wave 1 — Parallel Specialist Work

Run Agents 1–5 in parallel against the frozen contracts.

Parallelism is allowed because ownership is separated:

- Agent 1: import/canonicalization;
- Agent 2: serving/search;
- Agent 3: question-detail/user persistence;
- Agent 4: execution/judge integration;
- Agent 5: attempt/progress projection.

If an agent needs a shared contract change, stop and route it through Agent 0 rather than independently modifying the interface.

## Wave 2 — Integration + E2E

Agent 0 merges in dependency order. Agent 6 runs continuously after each integration merge and owns the final release report.

## Wave 3 — Only After Core Milestone PASS

Do not start these until search → solve → submit → persist is proven:

1. full conversational AI tutor/interviewer;
2. adaptive mastery/readiness and spaced repetition;
3. company intelligence and role/topic frequency signals;
4. full Admin Content Factory;
5. broader production deployment/IaC closure;
6. deeper AI retrieval/citation evaluation;
7. certification/company SEO content expansion.

---

# PR / Branch Naming

Recommended workstream branches:

- `agent/1m-corpus-ingestion`
- `agent/live-question-bank-search`
- `agent/question-detail-persistence`
- `agent/runtime-judge-wireup`
- `agent/attempts-progress-foundation`
- `agent/milestone-e2e-release`

Every PR body must include:

- scope;
- contracts consumed;
- files/tables owned;
- migrations added;
- tests added;
- physical counts where applicable;
- security/provenance implications;
- known blockers;
- explicit non-goals.

---

# Required Agent Status Format

Every agent must publish machine-readable and human-readable status:

```text
Agent: <name>
Branch: <branch>
Head SHA: <sha>
Status: PASS | BLOCKED | FAIL
Implemented: <facts only>
Tests: <facts only>
Physical counts: <actual measurements only>
Blockers: <external/internal blockers>
Contract changes requested: <none or details>
Next integration dependency: <agent/PR>
```

Definitions:

- **PASS** = workstream acceptance criteria proven.
- **BLOCKED** = required external artifact/evidence is absent; implementation may be correct but milestone cannot be asserted.
- **FAIL** = supplied evidence contradicts expected contracts or tests fail.

---

# Final Product Acceptance Scenario

A fresh authenticated user must be able to:

1. enter the product;
2. search the actual serving corpus for a term such as `Snowflake warehouse contention`;
3. apply `Snowflake` + `Hard` + a real status/topic filter;
4. open an arbitrary database-backed published question;
5. see the real problem/runtime contract;
6. edit Python or SQL in the coding pad;
7. Run public tests;
8. Submit against hidden validation;
9. receive a deterministic result;
10. refresh the page and recover the attempt/result;
11. see the attempt reflected in progress/history;
12. open a reference-only item and confirm execution is unavailable;
13. repeat with another authenticated user and prove isolation.

Until this scenario passes against the aggregate branch, the milestone is not complete.

---

# Final Instruction to All Agents

Do not optimize for the appearance of progress. Optimize for **provable, reviewable product truth**.

The objective is to cross the line from "the repository contains a large source corpus and an impressive application foundation" to "SkillForge actually serves the real corpus and supports a real, durable solve workflow end to end."
