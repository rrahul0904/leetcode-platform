# Security Model

## Identity

Amazon Cognito provides OAuth 2.0/OIDC Authorization Code with PKCE, verified email, MFA support, recovery, and short-lived tokens. The application stores no passwords. Local automation uses a controlled OIDC issuer and the same JWT validation path.

## Authorization

Roles are candidate, content author, technical reviewer, editorial reviewer, interviewer, organization administrator, platform administrator, support administrator, and read-only auditor. Enforcement occurs in API dependencies, domain services, tenant-scoped queries, PostgreSQL RLS where applicable, and S3 policies. Route hiding is cosmetic only.

## Data protection

TLS in transit, KMS-backed encryption at rest, Secrets Manager, tenant-aware object keys, least-privilege roles, retention and deletion workflows, PII redaction, consent records, signed URLs, secure cookies, CSP, request/output limits, and immutable audits for sensitive administration.

## Content and model safety

Candidate-safe projections prevent hidden-content leakage. All provider calls use the AI gateway, explicit consent, redaction, tenant limits, bounded retries, and auditable prompt/model metadata. Provider output cannot publish or override deterministic correctness.

