# Real-SWE Competitive Build — Phase 2

## Objective

Move PR Review Lab from a browser-only vertical slice to a candidate-owned, server-backed review workflow without exposing the hidden grading rubric in the client bundle.

## Implemented

- Alembic revision `20260914_0020` adds candidate-owned `pr_review_sessions` and `pr_review_comments`.
- Both tables use PostgreSQL row-level security with `FORCE ROW LEVEL SECURITY` and the existing `rigor.user_id` principal boundary.
- Authenticated API endpoints load the public challenge, create/list/restore sessions, persist/remove comments, and submit the final merge verdict.
- The hidden findings and deterministic grading algorithm now live only in the API package.
- Browser code receives the public diff before submission and receives hidden finding explanations only after the server scores a submitted review.
- Active sessions restore after refresh so review comments are durable rather than component-local state.
- Domain tests cover challenge secrecy, diff-line validation, full deterministic scoring, and unknown-challenge rejection.
- Web interaction coverage mocks the API boundary and verifies session creation, persisted comments, and server-supplied grading.

## Security boundary

The browser no longer contains the gold findings or grading function. Review comments are validated against known lines in the server-owned challenge before persistence. Submitted sessions are immutable through the review API, and ordinary users can only see rows owned by their authenticated principal.

The grading algorithm remains deterministic. AI-generated qualitative feedback can be added later, but it is not required for correctness or release certification.

## Migration and release contract

The release workflows must migrate PostgreSQL to `20260914_0020` and verify both PR-review tables before any production web promotion. Production remains fail-closed if the database head, table inventory, or forced-RLS checks do not match the source candidate.

## Next phase

1. Add challenge catalog, attempt history, progression, and XP.
2. Add GitHub-backed repository ingestion and repository-interview generation.
3. Add multi-file engineering missions backed by ephemeral execution environments.
4. Add qualitative AI feedback after deterministic grading completes.
