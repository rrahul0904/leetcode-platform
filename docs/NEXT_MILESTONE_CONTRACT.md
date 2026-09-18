# SkillForge / Rigor — Next Milestone Contract

Status: **FROZEN FOR WAVE 1**

Integration branch: `agent/next-milestone-multi-agent`
Source base: `agent/question-bank-coding-pad`

This document freezes the shared interfaces for the real-corpus solve-flow milestone. Specialist branches may implement behind these contracts, but any shared-interface change must return to Agent 0 for review.

## 1. Product boundary

The aggregate milestone is complete only when an authenticated candidate can:

`Question Bank -> database search/filter -> arbitrary candidate-visible question -> create/recover practice session -> Run public tests -> Submit hidden validation -> retrieve terminal result -> reload -> recover attempt/progress`.

The same flow must work for one Python question and one PostgreSQL question. A reference-only question must be visible as reference material but must not be able to create a practice/execution job.

## 2. Existing systems are canonical

Do not replace these existing foundations:

- normalized authored content: `questions`, `question_versions`, `solutions`, `rubrics`, provenance/publication tables;
- imported/source-backed corpus: `knowledge_sources`, `knowledge_source_files`, `knowledge_problems`, `knowledge_problem_sources`, topics, companies, solution approaches/variants;
- candidate knowledge state: `knowledge_candidate_problem_state`, `knowledge_activity_events`;
- durable practice state: `practice_sessions`, `practice_session_events`;
- durable execution plane: `execution_requests`, execution queue/controller, public execution results, isolated Python runner, isolated PostgreSQL execution database;
- authenticated database context and existing RLS/principal-transaction model.

Candidate Python/SQL must never run in Next.js or normal FastAPI application workers.

## 3. Source and rights states

Existing `knowledge_sources.disposition` values remain authoritative:

- `hostable_licensed`
- `external_reference_only`
- `rights_review_required`
- `rejected_proprietary`

Rules:

1. A source being physically present does not grant publication rights.
2. `external_reference_only` may support IDs, titles, URLs, company/frequency observations, and other safe metadata; it does not authorize copying protected statement/solution bodies.
3. `rights_review_required` is fail-closed for hosted body/solution publication.
4. `rejected_proprietary` cannot become candidate-hosted content.
5. Publication/review gates already present in the repository must not be weakened.

## 4. Corpus classification contract

The large-corpus importer must classify each accepted source row using one of these values:

- `canonical_candidate`
- `legitimate_variant`
- `near_concept_duplicate`
- `reference_only`
- `runnable_candidate`
- `review_required`
- `rejected_quarantined`

These are import/canonicalization classifications, not permission grants.

A record may be a `runnable_candidate` only when its content contract is structurally capable of becoming a runtime package. It is **not runnable to a candidate** until the runtime-link contract below is verified.

## 5. Candidate visibility contract

Candidate-facing APIs must never expose quarantined/rejected/review-only material by default.

Derived candidate availability is frozen as:

- `runnable`: candidate-visible published content with an **active verified runtime link** to the current published authored question version.
- `published`: candidate-visible hosted content that is legitimately published but has no active verified runtime link.
- `reference_only`: candidate-visible reference metadata whose source disposition permits reference use but not hosted/runnable publication.
- `review`: admin/reviewer-only state. Normal candidate search/detail must not return it.
- `quarantined`: admin-only. Normal candidate search/detail must not return it.

Important: the current knowledge-catalog heuristic that treats an approved executable solution as sufficient for `runnable` is not sufficient for this milestone. Agent 2 must switch candidate `runnable` derivation to the verified runtime-link contract once Agent 1's shared migration is integrated.

## 6. Runtime-link contract

Wave 1 uses one explicit bridge between imported/searchable corpus items and authored executable packages.

Agent 1 owns migration `20260824_0016_large_corpus_serving.py` (down revision `20260802_0015`). It must include the shared runtime bridge so no parallel migration collides.

Required logical table:

`knowledge_problem_runtime_links`

Required fields/invariants:

- `problem_id` -> `knowledge_problems.id`, unique/primary logical identity;
- `question_id` -> `questions.id`;
- `question_version_id` -> `question_versions.id`;
- `runtime` (`python` or `postgresql` for this milestone);
- `link_status` (`review`, `verified`, `revoked`);
- `package_hash` or equivalent immutable runtime-package identity;
- `verified_at`;
- provenance/audit metadata sufficient to identify how the link was established.

A `verified` link must fail validation unless all are true:

1. `questions.current_published_version_id == question_version_id`;
2. linked `question_versions.state == published`;
3. runtime is supported by existing `question_runtime()`;
4. a supported starter source exists;
5. at least one public test exists;
6. at least one hidden test exists for Submit acceptance;
7. the execution entrypoint/SQL DDL+seed contract validates;
8. the knowledge problem is legitimately candidate-visible under source/publication rules.

Revoking or republishing the authored question must make stale links non-runnable until reverified.

## 7. Large-corpus import batch contract

The physical 100K/1M Parquet/JSONL artifacts are import inputs, not runtime stores.

Importer inputs must include:

- corpus/version identifier;
- manifest path/hash;
- source file path;
- source file SHA-256 when available;
- physical row count from file metadata;
- batch ID;
- bounded batch size/checkpoint;
- source rights/disposition evidence.

Per accepted row preserve at minimum:

- original source ID;
- source file and source-row locator;
- batch/import ID;
- corpus version;
- content fingerprint;
- canonicalization classification;
- original source metadata needed for audit;
- rights/publication disposition.

Required reconciliation counters are physical facts only:

- physical_source_rows
- parsed
- validated
- rejected
- duplicate_ids
- duplicate_fingerprints
- canonical
- variants
- near_duplicates
- review_required
- reference_only
- runnable_candidates
- published
- runtime_verified

Running an already completed batch twice must not duplicate serving records or associations.

If physical large-corpus files cannot be located, Agent 1 reports `BLOCKED`; it must not regenerate substitute rows.

## 8. Search contract

Candidate endpoint remains under `/knowledge/catalog` unless Agent 0 approves a versioned replacement.

Candidate search request supports the data actually present, with stable server-side pagination/sorting. Required milestone filters:

- free-text query;
- difficulty;
- runtime/language;
- topic;
- subtopic when imported metadata contains it;
- company;
- platform when imported metadata contains it;
- seniority when imported metadata contains it;
- industry when imported metadata contains it;
- availability (`runnable`, `published`, `reference_only`).

Admin/reviewer-only APIs may additionally filter `review` and `quarantined`.

Candidate result contract must include:

- stable problem ID;
- canonical key;
- slug;
- title/summary;
- difficulty;
- candidate availability;
- publication/review metadata safe for candidate display;
- runtime/languages;
- topics/company observations when present;
- runtime question slug or a separate `practice_target` only when availability=`runnable`.

Search must be database-backed. Hardcoded/demo arrays cannot be the serving source of truth.

Full-text search may use existing PostgreSQL tsvector/GIN indexes. Hybrid/vector search may only search rows with real embeddings and must report actual embedding coverage.

## 9. Question-detail contract

Candidate route may use `/knowledge/catalog/problems/{slug}` or a web alias `/questions/{slug}` backed by that API.

Candidate detail must return only candidate-visible records and include applicable:

- problem statement/description;
- constraints/examples/input/output/schema metadata;
- difficulty/topics/company signals;
- publication/availability;
- runtime/practice target only for verified runnable links;
- bookmark/notes/current candidate state;
- attempt/history summary from authenticated persisted state;
- solution/editorial availability flags, with body exposure still subject to publication rules.

Guessed review/quarantine/deleted URLs return 404 to a normal candidate. Reference-only detail returns content/metadata allowed by its source disposition and **never** a practice target.

## 10. Run / Submit contract

Reuse existing practice/execution APIs and models; do not invent a second runner API.

Canonical sequence:

1. Create/recover `practice_session` for the linked authored question slug/runtime.
2. `Run` uses the existing `PracticeRunRequest` + `Idempotency-Key` flow and queues an `ExecutionType.run` request.
3. Run passes only public tests to the isolated runner.
4. `Submit` uses `PracticeSubmitRequest` + a distinct idempotency key and queues `ExecutionType.submit`.
5. Submit evaluates public + hidden tests inside trusted execution/evaluator paths.
6. Candidate result may expose public expected/actual details and only hidden aggregate counts; hidden inputs/expected outputs remain secret.
7. Execution status/result lookup remains candidate-scoped through existing authenticated DB context.
8. Duplicate keys with identical request hashes return the existing execution as duplicate; reusing a key for a different request is a conflict.
9. Refresh/reconnect recovers state from persisted practice/execution records, not browser-only state.
10. A non-runnable knowledge problem cannot create a practice session or execution request.

Existing backpressure, cancellation, lease, retry, DLQ, runner isolation and security boundaries remain in force.

## 11. Attempt and progress event contract

`knowledge_activity_events` remains append-only evidence; `knowledge_candidate_problem_state` remains the minimal projection.

Wave 1 event mapping:

- detail opened -> `problem_viewed`;
- draft persisted -> `draft_saved` only when a durable/server action occurs;
- successful accepted Run request/result -> `public_tests_run` with execution ID/status metadata;
- terminal Submit -> `submission_completed` with execution/submission ID, runtime, terminal status;
- terminal passing Submit -> `problem_solved`;
- terminal failing Submit -> `problem_failed`;
- bookmark mutation -> `bookmark_changed`;
- note mutation -> `notes_saved`;
- reliable elapsed-time update -> `session_time_recorded`.

Idempotency rule: event idempotency keys must be derived from the durable business event identity (for example `submission:<submission_id>:completed`) so duplicate delivery cannot double-count progress.

Wave 1 progress is deterministic evidence only:

- attempts;
- solves/failures;
- recent activity;
- time spent where reliable;
- topic/subtopic evidence derived from the served problem associations.

No invented mastery/readiness percentage is part of this milestone.

## 12. User isolation

All candidate private state remains candidate-scoped.

Mandatory negative tests:

- User A cannot read/update User B practice session;
- User A cannot read User B execution result;
- User A cannot read/update User B bookmark/note/problem state;
- guessed unpublished/review/quarantine question URL is not exposed to a normal candidate.

Existing RLS and `principal_transaction()` session context are the preferred enforcement mechanism.

## 13. Migration allocation

Current integration-base migration head: `20260802_0015`.

Frozen allocation for this wave:

- Agent 1: `20260824_0016_large_corpus_serving.py` — owns large-corpus serving metadata/indexes, import batch/checkpoint support needed beyond existing tables, and `knowledge_problem_runtime_links`.
- Agents 2–5: **no schema migration by default**. Reuse 0016 + existing schema. If a migration becomes unavoidable, request Agent 0 approval before creating it.
- Agent 6: no product-schema migration.

This avoids parallel Alembic heads.

## 14. Branch ownership and merge order

Wave 1 branches:

1. `agent/1m-corpus-ingestion`
2. `agent/live-question-bank-search`
3. `agent/question-detail-persistence`
4. `agent/runtime-judge-wireup`
5. `agent/attempts-progress-foundation`

Wave 2:

6. `agent/milestone-e2e-release`

Integration order:

1. Agent 1 shared migration/import contracts;
2. Agent 2 serving/search using 0016;
3. Agent 3 detail/persistence;
4. Agent 4 runtime wiring;
5. Agent 5 progress projection;
6. Agent 6 aggregate proof.

Agent 2–5 branches may code against this frozen interface in parallel, but their final integration PRs must rebase onto the integrated Agent 1 migration before PASS.

## 15. Physical corpus evidence available at contract freeze

Repository/source-bank work proves a smaller reviewed source-backed corpus and explicit fail-closed external evidence gates. The newly supplied 100K/1M manifests describe audited source-bank row counts, but the physical 1M Parquet files have not been located in the GitHub repository or current accessible File Library during Agent 0 contract freeze.

Therefore Agent 1 starts implementation work but its corpus-import acceptance status remains `BLOCKED` until physical files are supplied/located and hash/row verification is performed. Manifest targets alone are not accepted as database/import proof.

## 16. FDAI generation package

The supplied Forward Deployed AI Engineer package is a valid **generation/import specification**, not proof that its 90K+ target corpus physically exists.

The specification requires nine core categories at 10,000 each, complete solutions, deterministic 100–250 record batches, stable scenario fingerprints, JSON Schema validation, and physical output counts. It may be used as a future/parallel source producer feeding the same large-corpus importer, but no generated target count may be reported as completed until physical files and batch manifests exist.

For this milestone, FDAI content generation must not delay the core real-corpus search -> solve -> submit -> persist flow.

## 17. PASS / BLOCKED / FAIL

- `PASS`: workstream acceptance criteria are proven with code/tests/physical evidence.
- `BLOCKED`: implementation can proceed, but required external corpus/rights/runtime evidence is missing.
- `FAIL`: implementation or supplied evidence contradicts the frozen contract or tests fail.

No agent may convert BLOCKED to PASS by weakening a requirement.
