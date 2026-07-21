# User Journeys

## Candidate preparation

1. Sign in through OIDC and complete target-role, timeline, availability, and consent onboarding.
2. Receive a provisional plan explicitly separated from performance-evidenced recommendations.
3. Filter published questions by role, track, skill, difficulty, prerequisite, and independent company style.
4. Practice in the appropriate workspace, autosave, submit, and receive deterministic results before AI commentary.
5. Review evidence-linked rubric scores, missed requirements, remediation, and spaced repetition.

## Content publication

1. Author creates a version from a manifest entry.
2. Automated schema, reference, executable, rubric, originality, and similarity checks run.
3. A technical reviewer approves or requests revision.
4. A different editorial reviewer approves or requests revision.
5. Publishing workflow records the Git revision, hash, approvals, and idempotently synchronizes PostgreSQL.
6. Later changes create a version; historical submissions retain the prior version.

## Account deletion

The user requests deletion, receives a durable workflow ID, and can export data before the retention window ends. The workflow revokes sessions, deletes or anonymizes tenant-scoped records according to legal policy, removes objects, and records a non-PII completion audit.

