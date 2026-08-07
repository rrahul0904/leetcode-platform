# Source-backed question bank

Generated from the 11 user-provided archives and integrated with Rigor's native PostgreSQL knowledge bank.

## Generated inventory

- 3,424 company-indexed questions
- 1 additional statement-backed problem absent from the company CSVs
- 3,425 total searchable problems
- 121 statement-backed candidates
- 120 reference solutions
- 1,063 unique solution slugs across the uploaded repositories
- 29 system-design resources
- 35,348 normalized company-to-question associations
- 92,728 deduplicated source CSV rows

## Runtime model

The complete generated ZIP is installed as:

`content/imported/source-backed/question-bank.zip.b64`

The importer projects it into existing native tables:

- `knowledge_problems`
- `knowledge_topics`
- `knowledge_problem_topics`
- `knowledge_companies`
- `knowledge_company_observations`
- `knowledge_solution_approaches`
- `knowledge_solutions`
- `knowledge_system_design_articles`
- source-file and import-run audit tables

The process is deterministic and idempotent. Re-importing the same corpus returns `already_imported` instead of creating duplicates.

## Two separate content lifecycles

The source-backed bank deliberately separates searchable knowledge records from native executable packages.

### Searchable corpus

The complete source-backed archive contains the 3,425 searchable records and their normalized company, topic, solution, provenance, and system-design projections. A production-ready PR checkout must contain this archive, or contain canonical normalized inputs that deterministically reproduce it.

### Python review packages

The 20 checksum-pinned `IMP-*` Python packages are review-stage artifacts. They materialize under:

`content/imported/source-backed/materialized/python`

They **must not** be installed into `content/questions`. The canonical content synchronizer treats `content/questions` as Git-authored, manifest-approved content, so placing review-stage `IMP-*` packages there would correctly fail the publication/content-sync gate.

`make test-content` still schema-validates these quarantined packages and executes their reference test harnesses in isolated subprocesses. Quarantine therefore does not mean validation is skipped; it only prevents review material from being mistaken for approved candidate content.

## Installation and operator recovery

An operator can install a known generated archive with:

```bash
make install-question-bank BANK=/absolute/path/to/rigor_source_backed_question_bank.zip
make validate-question-bank
make assess-question-bank
make bootstrap
```

`make assess-question-bank` writes a ranked review queue to:

`content/imported/source-backed/readiness.json`

The report contains no copied source code or statements. It records availability, priority score, and the exact blockers preventing each candidate from becoming runnable.

When the bank is present before the Docker image build, `make bootstrap` imports it automatically and refuses to complete unless PostgreSQL contains at least:

- 3,425 searchable knowledge problems
- 100 company indexes
- 29 system-design resources

For an already-running stack:

```bash
make import-question-bank
```

## Release gates

There are intentionally two release commands:

```bash
make release-local
make release-check
```

`make release-local` proves the existing native local platform from a clean Docker volume: builds, health, execution services, data allocation, backup, and restore.

`make release-check` is the stronger PR gate. It fails immediately unless the complete repository-contained source-backed archive exists, then runs source/content validation and the complete local release gate. This prevents a branch from being called source-bank production-ready merely because an operator happened to have a local archive outside Git.

The operator installation command remains useful for recovery and development, but an external-only archive does **not** satisfy the production-readiness definition for PR #7.

## Candidate behavior

All 3,425 problem records are imported as searchable `metadata_only` knowledge records. Company, topic, difficulty, language, and frequency filters use PostgreSQL-backed native relationships rather than client-side JSON scanning.

The 120 reference solutions are stored for editorial and technical review but are not marked executable. They cannot be returned by the candidate solution endpoint until an independently validated test suite exists and the records pass the existing publication workflow.

## Runnable publication contract

A source-backed coding candidate remains `in_review` until all of the following are present and validated:

- a complete candidate-safe statement;
- an approved hostable-rights disposition;
- a supported runtime;
- starter code matching the invocation contract;
- public tests;
- hidden tests;
- a reference solution that passes every test;
- an editorial or independently authored explanation;
- explicit publication approval.

Only candidates with no remaining blockers are reported as `runnable`. The initial imported corpus is intentionally not promoted merely because a statement or solution file exists.

## Content validation

The dedicated content workflow runs `make test-content`.

That command:

1. reconstructs the checksum-pinned Python review batch;
2. materializes the 20 review packages into the quarantine tree;
3. verifies the materialized tree exactly matches the committed package archive;
4. schema-validates canonical packages and the quarantine tree;
5. executes all discovered reference test harnesses in isolated pytest subprocesses;
6. validates and assesses the complete source-backed archive when it is present.

No review package is copied into the canonical publication tree as part of this process.

## Regeneration

Run `scripts/build_uploaded_question_bank.py` against the source ZIP archives. The generator normalizes slugs, deduplicates repeated company datasets, preserves source archive/path provenance, extracts statements and preferred solutions, and separates searchable metadata from executable hosted content.

A regenerated complete corpus must be checked into the repository (or represented by deterministic canonical normalized inputs that reproduce the exact release artifact) before PR #7 can satisfy `make release-check`.
