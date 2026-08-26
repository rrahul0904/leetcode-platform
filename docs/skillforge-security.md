# SkillForge AI security baseline

## Non-negotiable controls

1. SkillForge PostgreSQL never stores passwords. Clerk/Auth0 owns credentials and MFA.
2. Candidate code never executes in Next.js or FastAPI.
3. Candidate-scoped PostgreSQL state uses row-level security where applicable.
4. S3 buckets are private; client access is via short-lived SigV4 URLs.
5. Redis/Valkey is ephemeral cache/coordination, never the authoritative candidate database.
6. Administrative/content mutations remain auditable.
7. Production secrets live in Secrets Manager and are injected into ECS tasks.
8. Production local OIDC and local execution adapters fail closed.
9. SQS delivery is treated as at-least-once; execution claiming and webhook handling are idempotent.
10. WAF, TLS, security groups, private subnets, encrypted data stores, image scanning, and SBOMs form the infrastructure baseline.

## Identity and authorization

Clerk owns password credentials, social identity, email verification, password reset,
MFA, and session lifecycle. SkillForge stores only the external identity subject plus
application profile/status data.

The production web application uses Clerk on Vercel. Browser requests go through the
same-origin `/api/backend/*` BFF. The BFF mints a short-lived Clerk JWT server-side and
forwards it to FastAPI; the Clerk bearer token is not copied into browser localStorage.
Set `RIGOR_BACKEND_ORIGIN` to the fixed HTTPS API origin and configure a Clerk JWT
template (default `skillforge-api`) whose audience matches backend `JWT_AUDIENCE`.

FastAPI treats external OIDC claims as authentication evidence, not SkillForge
authorization. After signature/issuer/audience/expiry validation, it resolves the
`sub` against `users.identity_subject` and loads account status, roles, permissions,
email/display identity, and requested organization membership from PostgreSQL.
Provider-supplied role claims therefore cannot escalate SkillForge privileges. The
controlled local OIDC provider may carry roles only in local development/test mode.

## Clerk webhook

The API validates Svix `svix-id`, `svix-timestamp`, and `svix-signature` headers using HMAC-SHA256 and a five-minute replay window. `identity_webhook_events.external_event_id` prevents duplicate processing.

`user.created` / `user.updated` synchronize the external subject, verified email and
display identity, assign the default candidate role, and initialize preferences.
`session.created` records a login event and updates `last_login_at`. Password material
is never written to SkillForge PostgreSQL.

## Files

`candidate_files` stores only metadata. Storage keys are user-scoped and unpredictable. Upload/download URLs expire after five minutes. Buckets block all public ACLs and public policies.
