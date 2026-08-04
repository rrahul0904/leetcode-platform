# Source-backed question bank

Generated from the 11 user-provided archives.

## Generated inventory

- 3,424 unique company-indexed questions
- 121 statement-backed hosted-question candidates
- 120 hosted candidates with a reference solution
- 1,063 unique solution slugs across the uploaded repositories
- 29 system-design resources
- 35,348 company-to-question associations
- 92,728 deduplicated company CSV rows

## Data files

The generated bank is stored under `content/imported/source-backed/`:

- `external_question_index_*.jsonl` — searchable company/problem metadata
- `hosted_question_candidates.jsonl` — imported statements, topics, company tags, explanations where available, and a preferred reference solution
- `system_design_resources.jsonl` — imported system-design markdown resources
- `manifest.json` — generated integrity counts

## Publication boundary

Imported statement-backed records begin as `imported-draft` with `runnable=false`. The uploaded repositories provide statements and solutions but do not contain a complete validated public/hidden test suite for every problem. They can be indexed and reviewed immediately; runnable hosted publication requires deterministic test generation and validation.

## Regeneration

Run `scripts/build_uploaded_question_bank.py` against the source ZIP archives. The generator normalizes slugs, deduplicates repeated company datasets, preserves source provenance, and keeps metadata-only references separate from hosted candidates.
