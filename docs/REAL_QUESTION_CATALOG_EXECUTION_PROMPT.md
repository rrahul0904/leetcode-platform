# Rigor Platform — Real Practice Question Catalog Execution Prompt

## Mission

Replace generic, placeholder, demo-only, or weakly specified practice content with original, production-quality Python, PostgreSQL, and system-design questions that run through Rigor's governed content pipeline.

Implement content, tests, validation, review metadata, publication support, and UI integration. Do not stop at an inventory or proposal.

## Non-negotiable rules

1. Do not hardcode question cards, expected answers, or mock catalog data into Web components.
2. Use `content/questions/<track>/<QUESTION-ID>/` as the authoring source and PostgreSQL as runtime catalog authority.
3. Preserve the existing manifest, taxonomy, versioning, sync, review, approval, and publication lifecycle.
4. Author original Rigor scenarios. Do not copy proprietary problem statements, examples, hidden tests, solutions, or rubrics from LeetCode, HackerRank, interview forums, employers, or paid courses.
5. External sources may inform aggregate competency coverage only. Record provenance and originality honestly.
6. Python and SQL questions require deterministic public and hidden tests plus an executable reference verification path.
7. Candidate code must continue to execute only through the isolated asynchronous execution plane.
8. SQL candidate queries must run only against disposable PostgreSQL, never application RDS.
9. Hidden expected answers must never enter the candidate sandbox or candidate-visible API projection.
10. System-design questions require quantitative scale, SLOs, APIs, data models, diagrams, failure injection, security boundaries, observability, migration, and a scenario-specific 100-point rubric.
11. Every published question must be useful without relying on unstated interviewer knowledge.
12. Do not mark content production-ready unless schema, references, tests, duplicate checks, rubric checks, and repository CI pass.

## Phase 1 — Audit the current catalog

Inspect:

```text
content/question-bank-manifest.json
content/questions/**
content/external/**
packages/question-schema/**
apps/api/src/rigor_api/content_sync.py
scripts/sync_content.py
scripts/publish_local_catalog.py
scripts/start-populated-local
apps/web/**question**
```

Classify each authored package as:

```text
REAL_AND_EXECUTABLE
REAL_BUT_NEEDS_DEPTH
GENERIC_TEMPLATE
DEMO_ONLY
INVALID_OR_INCOMPLETE
```

Reject content that merely says "write a production-quality query," "design a production-grade system," or "discuss trade-offs" without exact business rules, constraints, failure cases, and evaluation evidence.

## Phase 2 — Python question standard

Each Python package must include:

- a concrete engineering scenario;
- exact function/class/API contract;
- deterministic input and output behavior;
- boundary and invalid-input semantics;
- time and memory limits;
- starter code;
- reference implementation or reference verifier;
- at least two public examples;
- hidden edge, adversarial, and invariant tests;
- complexity expectations;
- production follow-ups that do not alter the base coding contract;
- a scenario-specific rubric totaling 100 points.

Preferred competencies include:

- data structures and algorithms;
- concurrency and async coordination;
- streaming and bounded-memory processing;
- caching and expiration;
- scheduling and dependency graphs;
- reliability utilities;
- data-engineering transformations.

Tests must detect implementations that pass examples but violate the stated invariant.

## Phase 3 — PostgreSQL question standard

Each SQL package must include:

- a realistic business question;
- explicit PostgreSQL dialect;
- complete DDL and seed data;
- exact output columns, types, ordering, and null behavior;
- duplicate, late-arrival, eligibility, and boundary semantics where relevant;
- deterministic comparison mode;
- public and hidden fixtures with concrete expected rows;
- a reference query exercised by automated tests;
- statement timeout;
- production reasoning about indexes, partitions, cardinality, and incremental computation;
- a scenario-specific rubric totaling 100 points.

Do not use vague hidden tests containing only prose such as "stable ordering". Hidden fixtures must represent actual input and expected output while remaining unavailable to candidates.

Expected answers remain in the trusted evaluator. The disposable SQL sandbox receives schema, fixtures, and candidate SQL—but not expected result rows.

## Phase 4 — System-design question standard

Each system-design package must specify:

- users, tenants, traffic, fan-out, object sizes, and retention;
- availability and latency SLOs;
- functional and non-functional requirements;
- API contracts and idempotency semantics;
- logical data model and state machines;
- component, data-flow, and trust-boundary diagrams expected from candidates;
- capacity calculations with enough values to verify arithmetic;
- consistency, ordering, retry, and duplicate-handling requirements;
- overload, fairness, quota, and backpressure behavior;
- security, privacy, secrets, audit, and regional-residency boundaries;
- observability, runbooks, ownership, and cost controls;
- at least five concrete failure injections;
- at least two requirement changes;
- migration and rollback expectations;
- a scenario-specific 100-point rubric.

A generic queue-and-worker diagram or unquantified technology list must score poorly.

## Phase 5 — Package integrity

For every changed package update all applicable files together:

```text
question.json
metadata.json
rubric.json
solution.md or reference.sql
public tests
hidden tests
test_reference.py
```

Increment the content version when modifying published or reviewed material. Preserve immutable history in the database sync model.

Metadata must include:

- originality statement;
- authoring method;
- source classes;
- source notes;
- author identity;
- authored timestamp;
- validation status;
- review status;
- content version.

Never claim a content hash or validation run completed when it has not. Generate hashes and update validation fields through the repository's validation workflow.

## Phase 6 — Catalog and UI integration

The Web catalog must read the real API catalog. Do not add fallback mock questions when the API is empty or unavailable.

Use honest states:

```text
loading
empty catalog
API unavailable
no filter results
question unpublished
question runtime unavailable
```

The dashboard, catalog, question detail, practice workspace, learning paths, and mock interviews must display the same canonical question identity and version.

## Phase 7 — Regression gates

Add automated tests that fail when flagship Python, SQL, or system-design packages regress to generic templates.

At minimum assert:

- required package files exist;
- JSON parses;
- IDs and slugs match the package;
- rubric weights total 100;
- Python and SQL have concrete public and hidden tests;
- SQL has executable DDL, seed data, expected results, and reference query;
- system design has quantified scale, SLOs, capabilities, failure scenarios, requirement changes, and expected artifacts;
- placeholder phrases and TODO markers are absent;
- hidden expected answers are not exposed through candidate API fixtures.

## Phase 8 — Validation

Run the exact repository gates, including:

```bash
uv sync --frozen --all-packages
uv run ruff check apps/api/src packages/question-schema/src scripts apps/api/tests packages/question-schema/tests tests content/questions
uv run pyright apps/api/src packages/question-schema/src scripts
uv run pytest -q

pnpm install --frozen-lockfile
pnpm --filter @rigor/web lint
pnpm --filter @rigor/web typecheck
pnpm --filter @rigor/web test
pnpm --filter @rigor/web build

python scripts/sync_content.py
python scripts/verify_reference_tests.py
python scripts/publish_local_catalog.py
```

Also retain migration, Terraform, Packer, image-build, vulnerability-scan, SBOM, and signing gates where the branch requires them.

Do not weaken a failing quality or security gate.

## Phase 9 — Publication and merge

Before merge:

1. sync changed content into a clean local PostgreSQL database;
2. run all executable reference tests;
3. verify schema and taxonomy references;
4. move content through review and approval using the existing workflow;
5. verify the published API returns the new versions;
6. verify Web catalog/detail/practice pages use those API records;
7. get aggregate CI green;
8. update the pull-request description with question IDs, versions, validation, and provenance;
9. mark the PR ready only after all required checks pass;
10. merge without bypassing branch protection.

## Required completion report

Report:

- question IDs, titles, tracks, versions, and publication status;
- package files changed;
- public and hidden test counts;
- reference-verification results;
- catalog/API/UI evidence;
- exact validation commands and results;
- CI run number and every job conclusion;
- provenance and originality statement;
- PR number and merge commit SHA;
- any remaining content, staging, or operational gaps.

Use only these status labels:

```text
IMPLEMENTED
VALIDATED LOCALLY
VALIDATED IN CI
PUBLISHED
MERGED
BLOCKED
NOT IMPLEMENTED
```
