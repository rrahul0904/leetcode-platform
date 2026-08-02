# Phase 0–6 Implementation Status

Updated: 2026-08-01

This document separates implemented source, local execution evidence, GitHub CI evidence, and work that still requires a deployed staging environment.

## Phase 0 — Execution contract stabilization

**Status: implemented and CI validated**

- VPC CNI NetworkPolicy enforcement is enabled in the EKS add-on configuration.
- Legacy Python packages derive one unambiguous top-level function entrypoint.
- Python invocation supports automatic, keyword-argument, positional-argument, single-payload, and no-argument modes.
- Object inputs can call multi-parameter Python starters as keyword arguments.
- SQL tests apply per-test DDL, seed, and additive setup SQL.
- SQL practice sessions use the published question runtime as authority.
- Regression tests cover the five P1 findings carried forward from PR #1.

Live AWS/EKS/gVisor isolation remains a staging verification requirement.

## Phase 1 — Uploaded archive inventory and extraction

**Status: implemented and executed against the uploaded corpus**

- All 11 uploaded ZIP files are inventoried by SHA-256, size, entry count, and suffix distribution.
- One exact duplicate company archive is detected and processed once.
- Extraction rejects traversal paths, symbolic links, excessive expansion, suspicious compression ratios, and excessive entry counts.
- Executables, compiled files, PDFs, and nested archives are quarantined rather than parsed or executed.
- Source-specific parsing covers numbered problem folders, multi-language solution folders, company CSVs, competitive-programming resources, and system-design Markdown.
- Every parsed observation retains source archive, source path, source hash, and source disposition.

## Phase 2 — Canonical PostgreSQL knowledge model

**Status: implemented and migration validated**

The schema includes:

- source archives, source files, and import runs;
- canonical problems and source observations;
- topics and problem-topic mappings;
- solution approaches and multi-language solution variants;
- companies and time-windowed company-question observations;
- system-design articles and learning resources;
- full-text search documents and GIN indexes;
- candidate problem state and append-only activity events;
- candidate row-level security for notes, bookmarks, revision state, and activity.

The migration chain upgrades to `20260801_0014`, downgrades to `20260801_0013`, and re-upgrades to head in CI.

## Phase 3 — Transactional corpus import

**Status: implemented and locally validated with the actual uploaded corpus**

- The corpus importer runs in one controlled transaction.
- Re-importing the same corpus is idempotent by archive hash, file hash, canonical problem identity, solution hash, and company observation identity.
- Duplicate problem records merge metadata while preserving unique language solutions, approaches, topics, companies, and source observations.
- Source dispositions control whether a record is hostable, metadata-only, rights-review-required, or rejected.
- Imported records are not automatically published.
- The actual normalized upload corpus completed a fresh PostgreSQL import and a second idempotent import in local validation.

The raw ZIP files remain offline import inputs and audit artifacts; application clients read PostgreSQL APIs only.

## Phase 4 — Knowledge APIs

**Status: implemented and CI validated**

Candidate APIs provide:

- corpus statistics;
- searchable and paginated problems;
- difficulty, language, company, topic, and sort filters;
- canonical problem details;
- reviewed solution variants;
- company aggregates and company problem lists;
- topic aggregates;
- system-design library and article detail.

Administrative publication refuses problems without a hostable licensed source. Solutions become public only after review and publication.

## Phase 5 — Recording-inspired Web experience

**Status: implemented and Web build validated**

Routes include:

- `/problems` — searchable, URL-shareable question bank;
- `/problems/{slug}` — timed three-pane workspace;
- `/companies` — company preparation index;
- `/system-design-library` — reviewed system-design library;
- `/system-design-library/{slug}` — article study view.

The visual system follows the supplied recording's dark editorial experience:

- warm near-black surfaces;
- serif display hierarchy;
- uppercase monospaced metadata;
- restrained coral accents;
- persistent question navigator;
- active, flagged, reviewed, loading, empty, and error states;
- previous/next flow and timed sessions;
- responsive desktop and mobile layouts.

## Phase 6 — Persistent candidate evidence

**Status: implemented and connected to the workspace**

The problem workspace now records and persists:

- problem views;
- session starts;
- draft-save evidence;
- elapsed session time;
- bookmarks;
- private notes;
- revision status;
- attempts, failures, and solves when execution events are connected;
- language usage;
- current and longest streak inputs.

Candidate state is protected by forced PostgreSQL row-level security and cannot be read or changed by another candidate.

## Validation evidence

The current feature branch passes the required GitHub checks for:

- Python lint, strict Pyright, Pytest, execution-image builds, vulnerability scans, and SBOM generation;
- Web lint, TypeScript, component tests, and production build;
- PostgreSQL migration cycle and RLS checks;
- Terraform format and validation;
- Packer and gVisor installer validation.

A separate local validation report covers the downloaded branch and actual uploaded-corpus database import.

## Deliberate remaining limitations

1. Imported source observations are not all public hosted questions. Publication remains review- and rights-gated.
2. Imported solution files are not automatically executable. A hosted coding question still requires a canonical runtime, entrypoint, starter, public tests, hidden tests, limits, and trusted expected outputs.
3. The uploaded archives contain little structured SQL practice content. SQL expansion requires original PostgreSQL scenarios and tests rather than fabricated extraction claims.
4. System-design notes and images remain review-gated until their publication rights are established or Rigor-original articles replace them.
5. Live AWS SQS → controller → EKS → gVisor execution and adversarial isolation still require a deployed staging environment.
6. This phase does not implement the Expo iOS/Android client.

No source or CI evidence is described as staging-validated or production-verified without a live deployed environment.
