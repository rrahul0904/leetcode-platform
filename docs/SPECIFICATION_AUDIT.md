# Specification Audit

**Status:** accepted with recorded interpretations
**Reviewed:** 2026-07-20

## Binding decisions

1. The full product is a multi-milestone program. A usable application must not be represented as the complete question bank until at least 1,000 questions are published and validated.
2. The mandatory stack document supersedes the earlier “prefer” language where they differ.
3. The core begins as a modular monolith. Untrusted execution, durable workflow workers, and AI evaluation remain separate security or scaling boundaries.
4. Git is the reviewable source for platform-authored content. PostgreSQL is the runtime catalog. Publishing is a one-way, idempotent synchronization from an approved Git revision to PostgreSQL; runtime edits never silently rewrite Git.
5. Deterministic Python and SQL results outrank AI evaluations.
6. Company-style tags indicate original preparation relevance, never interview provenance or employer affiliation.

## Resolved sequencing conflict

The requested order places the manifest before the schema. A minimal manifest contract is defined first, the 1,350 entries are generated and validated, and the full content schema follows. This preserves the intended order while avoiding an untyped manifest.

## Open dependencies

| Area | Dependency | Treatment |
| --- | --- | --- |
| Cognito | AWS account, user-pool IDs, domains, callback URLs | Configuration boundary; local work uses a standards-compliant mock OIDC issuer. |
| Stripe | Account, products, prices, webhook secret | No checkout implementation until configured; entitlements remain server-owned. |
| Temporal Cloud | Namespace and credentials | Local server first; cloud configuration is production-only. |
| AI providers | Provider accounts and explicit user/tenant consent | Gateway interfaces may be built; no private data is sent by default. |
| Sandbox | EKS nodes that support the tested gVisor RuntimeClass | Local controller contract first; production completion requires isolation evidence. |
| Content review | Named technical and editorial reviewers | AI may draft but cannot satisfy independent approval. |

## Material risks

- The editorial workload for 1,350 complete packages is larger than the initial application build.
- A dual Git/database content model can drift without immutable source revision IDs and idempotent publication records.
- Secure arbitrary-code execution is a dedicated platform and security program, not a normal web request.
- Principal-level difficulty requires human calibration and later empirical recalibration.
- Company-style curation needs evidence notes to avoid unsupported claims.

## Deferred, not waived

Voice interviews, production cloud provisioning, payments, and full sandbox completion are later milestones. Their absence is recorded in `docs/PROGRESS.md`; no placeholder is described as production-ready.
