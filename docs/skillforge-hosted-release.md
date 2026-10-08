# SkillForge hosted release contract

This document records the minimum evidence required before the reconstructed SkillForge platform can be promoted from a preview deployment.

## Hosted architecture

- Vercel Services hosts the Next.js web service and FastAPI API service.
- Candidate code is never executed in the API process.
- Hosted candidate execution uses the `VERCEL_SANDBOX` adapter unless an explicitly configured Kubernetes/SQS execution plane is selected.
- A hosted request must fail closed before enqueue when the configured execution plane is unavailable.
- PostgreSQL is durable system-of-record state; Valkey/Redis is non-authoritative coordination/cache state.
- Local OIDC and local execution adapters are forbidden in staging and production.

## Release gates

A release is not ready merely because it builds. The exact candidate SHA must satisfy all of the following:

1. Python tests, type checking, Ruff, web tests/build, migration preflight, Terraform validation, and security assurance are green.
2. Production dependency scans contain no known unfixed release-blocking vulnerabilities.
3. The hosted database is reachable and the migration cycle succeeds against the target schema.
4. Production identity configuration is present; local OIDC is disabled.
5. The configured execution plane is healthy and discoverable before candidate work is accepted.
6. The exact Vercel preview deployment passes live smoke tests for health, authentication boundaries, practice-session creation, candidate run, execution polling, and submit.
7. At least one real Python execution reaches a terminal result through the isolated sandbox rather than the API process.
8. No preview deployment is promoted and no reconstruction PR is marked ready until the evidence above is attached to the exact SHA.

## Failure policy

Hosted configuration must fail closed. Missing database, identity, or sandbox credentials are deployment/configuration failures; the application must not silently fall back to localhost, local OIDC, or local candidate execution.
