# Deployment Blockers and Decisions

Updated: 2026-09-21

This file describes the current launch boundary. Historical readiness percentages and older
Cognito/early-corpus assumptions are not release instructions. See
[`LAUNCH_WEEK_2026-09-27.md`](LAUNCH_WEEK_2026-09-27.md) for the launch control record.

## Repository-certified state

- The launch catalog is an explicit allowlist of 50 first-party packages with schema and rights
  validation in the production release contract.
- Production identity uses Clerk; PostgreSQL remains authoritative for application roles,
  account status, entitlements, and candidate-owned data.
- The production release path is fail-closed, binds ECS and Vercel work to one immutable Git
  SHA, retains certification evidence, and targets the existing
  `skillforge-interactive-demo` Vercel project.
- The expected production Alembic head is `20260918_0021`.
- Current production Terraform defines the trusted application plane, including ECS, Aurora
  PostgreSQL, Valkey, SQS, S3, ECR, TLS/DNS, WAF, CloudWatch logs, Container Insights, and
  deployment rollback controls.
- Candidate code remains a separate trust boundary. Source and CI validation are not a
  substitute for live hostile-execution isolation evidence.

## Current P0 release blocker

The most recent authorized production-release attempt failed closed before any production
mutation because the GitHub Actions production secret `VERCEL_TOKEN` was not configured.

Do not bypass this check. Configure the credential in the GitHub production release boundary,
then rerun the hardened exact-SHA workflow.

## Production inputs that must be verified before cutover

The connected GitHub API used for repository work does not expose repository/environment
secrets, so the following values must be verified in GitHub rather than assumed present:

- `VERCEL_TOKEN`
- `AWS_REGION`
- `AWS_DEPLOY_ROLE_ARN`
- `ECS_CLUSTER`
- `ECS_API_SERVICE`
- `ECS_WORKER_SERVICE`
- `ECR_API_REPOSITORY`
- `ECR_WORKER_REPOSITORY`

The Vercel production environment must also provide the Clerk credentials, production
PostgreSQL URL, and a non-loopback HTTPS `RIGOR_BACKEND_ORIGIN` required by
`.github/workflows/deploy-vercel-skillforge.yml`.

## Live-production drift

As observed on 2026-09-21, the canonical Vercel hostname is serving a READY production
deployment built from Git SHA `7b64d7b3183eb0e6f5dba74ce0f83055b2da494a`, not the current
mainline release. That old deployment still exposes a localhost backend origin in its CSP.

The launch is therefore not production-certified until the hardened workflow deploys and
verifies one exact current release SHA end to end.

## Launch completion criteria

Production is complete only when the exact release SHA has evidence for:

1. production database migration to `20260918_0021`;
2. publication/verification of the audited 50-package launch catalog;
3. ECS API and trusted worker deployment from the same immutable SHA;
4. Vercel production deployment from the same immutable SHA;
5. canonical-host verification with no localhost/loopback backend origin;
6. production Clerk authentication;
7. representative Python and SQL Run/Submit flows with durable persistence;
8. candidate isolation checks and production runtime/error review;
9. retained release-certification evidence tying the SHA, ECS run, Vercel deployment,
   canonical URL, and database head together.

Do not weaken security or publication gates merely to meet the launch date.
