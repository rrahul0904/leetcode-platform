# Real-SWE Competitive Build — Phase 1

## Objective

Add a production-quality **PR Review Lab** to SkillsForge AI as the first implementation wave from the Real SWE teardown. The capability trains engineering judgment rather than algorithm recall.

## Shipped in this phase

- `/pr-review` candidate experience.
- Multi-file pull-request diff navigation.
- Line-level review comments.
- `info`, `minor`, `major`, and `blocker` severity calibration.
- Merge verdict: approve, comment, or request changes.
- Deterministic hidden-rubric grading with recall, precision, severity accuracy, reasoning quality, and verdict accuracy.
- A realistic payments/retry challenge with defects spanning idempotency, transactional ordering, and webhook verification.
- Responsive review UI and component test coverage.

## Architecture choice

This phase is intentionally self-contained in the web application and requires no new service, database, secret, provider, or infrastructure dependency. The grading function is pure and deterministic so it is testable and cannot be blocked by an LLM provider.

The next server-backed phase should persist review sessions and move gold findings behind the API boundary before user-generated or competitive challenges are enabled.

## Next phases

1. Persist review sessions, comments, verdicts, and scores through the existing API.
2. Add challenge catalog + progression/XP and attempt history.
3. Add GitHub-backed repo ingestion and repository interview generation.
4. Add realistic multi-file engineering missions with ephemeral execution environments.
5. Add AI-assisted qualitative feedback only after deterministic grading is complete, treating model feedback as an enhancement rather than a release dependency.

## Release truthfulness

Phase 1 is a functional vertical slice, not a claim of Real SWE feature parity. It deliberately avoids external hosting or AI dependencies so repository certification can distinguish product-code readiness from deployment authorization and production configuration.
