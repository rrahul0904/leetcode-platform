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

The generated ZIP is installed as:

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

## Installation

```bash
make install-question-bank BANK=/absolute/path/to/rigor_source_backed_question_bank.zip
make validate-question-bank
make assess-question-bank
make bootstrap
```

`make assess-question-bank` writes a ranked review queue to:

`content/imported/source-backed/readiness.json`

The report contains no copied source code or statements. It records availability, priority score, and the exact blockers preventing each candidate from becoming runnable.

When the bank is installed before the Docker image build, `make bootstrap` imports it automatically and refuses to complete unless PostgreSQL contains at least:

- 3,425 searchable knowledge problems
- 100 company indexes
- 29 system-design resources

For an already-running stack:

```bash
make import-question-bank
```

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

## Release validation

The dedicated content workflow runs `make test-content`, which validates every native question package against the strict schema and executes each reference implementation in an isolated pytest subprocess. When the source-backed archive is installed, the same gate validates the archive and generates its readiness report.

## Regeneration

Run `scripts/build_uploaded_question_bank.py` against the source ZIP archives. The generator normalizes slugs, deduplicates repeated company datasets, preserves source archive/path provenance, extracts statements and preferred solutions, and separates searchable metadata from executable hosted content.
