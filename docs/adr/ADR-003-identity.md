# ADR-003: V1 Identity and Candidate Ownership

- Status: Accepted; hosted journey pending
- Date: 2026-10-13

## Decision

Clerk is the external identity provider. The API verifies tokens server-side and reconciles a stable identity subject to one internal user/candidate record. All candidate-owned reads and writes enforce server-side ownership and PostgreSQL RLS; browser storage is not authoritative.

## Consequences

No client-provided candidate ID grants access. Admin/reviewer roles are checked server-side. Certification must include sign-up/sign-in/logout/re-login, missing/invalid/expired token, duplicate reconciliation and direct database cross-candidate isolation tests. Live Preview evidence is currently unavailable behind SSO.
