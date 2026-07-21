# Content Quality Gates

## State machine

`draft → generated → awaiting_technical_review → awaiting_editorial_review → approved → published`

Failure and terminal states are `automated_validation_failed`, `deprecated`, and `archived`.

## Publication gates

1. Schema completeness and stable identifiers
2. Slug, prerequisite, relation, role, skill, and tag integrity
3. Originality and provenance metadata
4. Deterministic duplicate and semantic-similarity thresholds
5. Reference solution and public/hidden test execution where applicable
6. Complexity-claim and expected-output review
7. Rubric completeness and weight total validation
8. Difficulty and seniority calibration
9. Independent technical approval
10. Independent editorial approval
11. Immutable source revision and content hash
12. Idempotent publication into PostgreSQL

AI output can enter `generated` only. It cannot approve, publish, overwrite deterministic results, or create unsupported company claims.

## Count semantics

- **Planned:** entry exists in the 1,350-item manifest.
- **Complete:** full package exists and automated gates pass.
- **Validated:** technical and editorial approvals are present.
- **Published:** validated version is synchronized into the runtime catalog.

Product UI and reports must display these counts separately.

