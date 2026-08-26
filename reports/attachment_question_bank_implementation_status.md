# Attachment Question Bank Implementation Status

## Corpus

- Candidate-serving records: **11,979**
- Source-backed solutions: **11,979**
- Source-backed/extracted explanations: **11,979**
- Execution-readiness pass: **824 Python runnable**, **20 SQL PostgreSQL-confirmation candidates**, **19 PySpark fixture-only**

## Implemented release path

1. `build_attachment_practice_bank.py` — source-backed normalized practice bank.
2. `build_attachment_execution_bank.py` — fail-closed public/hidden test construction and reference validation.
3. `sync_execution_ready_attachment_question_bank.py` — governed PostgreSQL sync with runtime specs and skill/topic indexing.
4. `verify_attachment_question_bank_db.py` — exact-count, solution, explanation, search, filter, and test-coverage release gate.
5. `attachment_solution_routes.py` — solution reveal without hidden-test disclosure.
6. `execution_patches.py` — multi-argument Python functional-runner fix.
7. `promote_large_question_corpus.py` — quality-gated 100K/1M reservoir promotion.

## Fail-closed runtime policy

- Python is runnable only after the source reference solution passes the source example plus at least one generated hidden test.
- SQL local relational prechecks are not sufficient for publication as runnable; PostgreSQL confirmation is required.
- PySpark remains non-runnable until a Spark runtime and concrete source-grounded machine fixtures exist.
- Reservoir promotion never auto-publishes content and never creates runtime links.

## Release proof required before calling the feature production complete

Run the sync against a migrated/seeded PostgreSQL application database, then execute:

```bash
make verify-attachment-question-bank-db EXPECTED=11979
```

The command fails unless all 11,979 questions, versions, solutions, explanations, and unique external IDs are present, search documents exist, subject filters return results, and every runnable question has both public and hidden tests.
