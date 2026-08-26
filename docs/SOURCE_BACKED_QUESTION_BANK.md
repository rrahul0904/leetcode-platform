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
make bootstrap
```

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

## Regeneration

Run `scripts/build_uploaded_question_bank.py` against the source ZIP archives. The generator normalizes slugs, deduplicates repeated company datasets, preserves source archive/path provenance, extracts statements and preferred solutions, and separates searchable metadata from executable hosted content.
