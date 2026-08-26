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

## Clerk webhook

The API validates Svix `svix-id`, `svix-timestamp`, and `svix-signature` headers using HMAC-SHA256 and a five-minute replay window. `identity_webhook_events.external_event_id` prevents duplicate processing.

## Files

`candidate_files` stores only metadata. Storage keys are user-scoped and unpredictable. Upload/download URLs expire after five minutes. Buckets block all public ACLs and public policies.
