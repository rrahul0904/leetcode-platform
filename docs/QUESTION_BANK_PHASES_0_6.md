# Rigor Question Bank: Phase 0–6 Working Plan

Updated: 2026-08-01
Branch: `agent/question-bank-phases-0-6`

This plan converts the uploaded LeetCode-style repositories and system-design archive into a governed PostgreSQL-backed knowledge bank focused on Python, SQL, JavaScript, and System Design. ZIP files are import inputs and audit artifacts only; the live application reads normalized records from PostgreSQL through FastAPI.

## Phase 0 — Stabilize the execution and product contract

Status: IN PROGRESS

- [ ] Fix question-driven runtime selection in the Web workspace.
- [ ] Fix Python entrypoint resolution for existing authored questions.
- [ ] Fix object test invocation as keyword arguments.
- [ ] Fix SQL per-test fixture parsing.
- [ ] Enable actual EKS VPC CNI NetworkPolicy enforcement.
- [ ] Add regression tests for all five P1 defects.
- [x] Create the Phase 0–6 implementation branch and working checklist.
- [x] Inventory all uploaded archives and identify the exact duplicate archive.

Exit gate: Python and PostgreSQL vertical slices execute correctly in tests; no unresolved P1 contract defect remains.

## Phase 1 — Source extraction, inventory, and ingestion framework

Status: NOT STARTED

- [ ] Add an offline operator CLI for large archives.
- [ ] Add safe extraction, path validation, archive/file hashing, and duplicate-archive detection.
- [ ] Add source manifests and import run reports.
- [ ] Add repository-specific adapters for problem folders, multi-language solution folders, Markdown catalogs, company CSVs, competitive-programming resources, and system-design notes.
- [ ] Quarantine binaries, nested archives, PDFs, and unsupported files.
- [ ] Preserve source archive, source file, source path, and content hash for every observation.

Exit gate: every uploaded archive can be scanned without executing source material, and malformed files do not terminate the complete import.

## Phase 2 — Canonical knowledge-bank schema and deduplication

Status: NOT STARTED

- [ ] Add normalized programming languages, topics, patterns, companies, problem identities, source observations, approaches, solutions, editorials, and company-frequency observations.
- [ ] Add unique constraints, foreign keys, GIN/trigram search indexes, timestamps, and review/publication state.
- [ ] Add deterministic identity resolution by external ID, URL slug, normalized title, and source hash.
- [ ] Add similarity-assisted duplicate review without automatic ambiguous merges.
- [ ] Preserve every unique approach and solution while maintaining one canonical problem.

Exit gate: repeated imports are idempotent and duplicate repositories do not create duplicate problems.

## Phase 3 — Import Python, JavaScript, company metadata, and original SQL

Status: NOT STARTED

- [ ] Import licensed/permitted Python and JavaScript solution variants with attribution and provenance.
- [ ] Import company/question/frequency information as source observations connected to canonical problems.
- [ ] Generate structured problem drafts from permitted descriptions and metadata.
- [ ] Build an original PostgreSQL SQL question pipeline because the uploaded archives contain little usable SQL question content.
- [ ] Keep rights-uncertain and premium-derived material metadata-only and review-gated.
- [ ] Produce counts for discovered, created, updated, merged, skipped, and failed records.

Exit gate: PostgreSQL contains real normalized records that appear through APIs; raw ZIP and extracted directories are not application runtime dependencies.

## Phase 4 — Candidate and admin APIs

Status: NOT STARTED

- [ ] Add problem search/list/detail endpoints with URL-shareable filters and cursor/page pagination.
- [ ] Add language, solution, editorial, hint, topic, pattern, company, and related-problem endpoints.
- [ ] Add company overview and preparation endpoints.
- [ ] Add system-design library endpoints.
- [ ] Add bookmark, note, revision, attempt, activity, and submission-history APIs.
- [ ] Add admin import-run, failure, duplicate-review, merge, publication, and re-index actions.

Exit gate: APIs expose complete normalized content and user state with authorization, validation, and structured errors.

## Phase 5 — Recording-inspired Web experience

Status: NOT STARTED

- [ ] Replace inconsistent candidate navigation with the recording-inspired dark editorial shell.
- [ ] Build landing/dashboard, Problems, Companies, Study Plans, Mock Exams, System Design, Resources, Journal, and Profile routes.
- [ ] Build Monaco-based Python/JavaScript and PostgreSQL workspaces.
- [ ] Add persistent question navigator, timer, flagging, previous/next, bookmark, revision, notes, tests, results, editorial, solutions, and submission tabs.
- [ ] Build the system-design requirements/canvas workspace.
- [ ] Add responsive, accessible loading, empty, error, success, keyboard, and mobile states.

Exit gate: a candidate can discover, open, practice, submit, review, bookmark, annotate, and revisit real database-backed content.

## Phase 6 — Progress intelligence, tests, and release validation

Status: NOT STARTED

- [ ] Add append-only activity events and projections for viewed, attempted, solved, failed, bookmarked, revision, language usage, time spent, streaks, topic/company/study-plan completion, and quiz performance.
- [ ] Add study plans, daily challenge, revision scheduling, quizzes, and evidence-backed recommendations.
- [ ] Add parser, normalization, dedupe, migration, API, authorization, search, frontend flow, accessibility, and browser E2E tests.
- [ ] Run Ruff, Pyright, Pytest, Web lint/typecheck/tests/build, migration cycle, container scans, and staging smoke validation.
- [ ] Update setup, ingestion, re-import, operations, deployment, limitations, and architecture documentation.

Exit gate: all quality gates pass on the exact branch head, imported data is visible in the UI, and remaining limitations are explicitly documented.

## Delivery policy

Each phase is implemented in order and kept reviewable. A later phase may add scaffolding, but it cannot be marked complete before the previous phase exit gate passes. Source implementation, CI validation, staging validation, and production verification are reported separately.
