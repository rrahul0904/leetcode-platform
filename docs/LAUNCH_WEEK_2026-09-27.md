# SkillForge Launch Week — target 2026-09-27

This document is the release control record for the one-week SkillForge launch. It replaces old percentage-based readiness snapshots as the operational source of truth.

## Release lineage

- Repository: `rrahul0904/leetcode-platform`
- Release branch: `agent/launch-week-2026-09-27`
- Branch point / certified main SHA: `a4565272fdc36498d0f081115e88154c270a7575`
- Canonical web hostname: `https://skillforge-interactive-demo.vercel.app`
- Current production deployment observed on 2026-09-21: Vercel deployment `dpl_8vEknv8ELjmHV9JDwAtBe2zt58BH`, built from old SHA `7b64d7b3183eb0e6f5dba74ce0f83055b2da494a`
- Current production therefore remains stale until an exact-SHA release completes.

## Launch scope

The launch release includes the current SkillForge / Rigor technical interview product:

- Clerk-authenticated candidate web experience
- governed first-party question catalog
- Python and SQL Run/Submit
- durable submissions, bookmarks, notes, progress, and evidence
- AI Tutor
- PR Review practice
- AI Arena
- Mock Interview
- Vercel candidate web
- ECS API and trusted worker
- PostgreSQL, Valkey, S3, SQS and the isolated execution boundary defined by the production infrastructure

CareerOS / resume / job-lifecycle functionality is not part of this release.

## P0 launch gates

All gates below must be green against the same immutable release SHA.

### Repository

- [x] Main CI green at branch point
- [x] Python test evidence green at branch point
- [x] immutable 40-character ECS release SHA enforced
- [x] exact checked-out SHA verified before AWS mutation
- [x] Vercel deployment metadata checked against the release SHA
- [x] production release evidence artifact retained for 90 days
- [x] first-party launch allowlist fixed at 50 packages
- [x] source-controlled launch content validates rights and schema
- [x] production database migration preflight exists through Alembic `20260918_0021`

### External production configuration

- [ ] GitHub production secret `VERCEL_TOKEN` is configured
- [ ] GitHub production variables are configured: `AWS_REGION`, `AWS_DEPLOY_ROLE_ARN`, `ECS_CLUSTER`, `ECS_API_SERVICE`, `ECS_WORKER_SERVICE`, `ECR_API_REPOSITORY`, `ECR_WORKER_REPOSITORY`
- [ ] Vercel production environment contains Clerk live keys (`pk_live_*` / `sk_live_*`), a non-loopback HTTPS `RIGOR_BACKEND_ORIGIN`, and a non-loopback production PostgreSQL URL
- [ ] AWS OIDC role trust permits this repository/environment
- [ ] ECS services, ECR repositories, database, cache, S3 and queues referenced by the release workflow exist
- [ ] production DNS/TLS for the API origin is valid

### Exact-SHA production release

- [ ] run `deploy-vercel-skillforge.yml` for the final immutable SHA
- [ ] production migration reaches `20260918_0021`
- [ ] production launch catalog publishes exactly the audited 50 packages
- [ ] ECS API and worker deploy the same release SHA
- [ ] ECS services are ACTIVE, running == desired, and PRIMARY rollout is COMPLETED
- [ ] Vercel production deployment reports the same Git SHA
- [ ] canonical hostname points to the new deployment
- [ ] no production CSP/backend origin references localhost or loopback
- [ ] retained production certification artifact identifies the same SHA, ECS run, Vercel deployment, canonical URL and Alembic head

### User-path verification

- [ ] landing page loads anonymously
- [ ] sign-up/sign-in works with the production Clerk live tenant
- [ ] candidate onboarding/profile persistence works
- [ ] question-bank search/filter/detail works
- [ ] at least one Python Run and Submit completes end to end
- [ ] at least one SQL Run and Submit completes end to end
- [ ] submission history/progress persists after reload
- [ ] bookmark and note flows persist
- [ ] Tutor starts and records a session
- [ ] PR Review starts and records feedback
- [ ] AI Arena can generate/submit/score through the governed execution path
- [ ] Mock Interview starts, accepts an answer and produces persisted state
- [ ] cross-candidate access checks remain denied
- [ ] production error scan shows no new P0/P1 runtime failures

## P1 launch-week hardening

These are required during the launch week but must not be allowed to silently expand the P0 scope:

- verify CloudWatch API/worker logs and ECS Container Insights after deployment
- capture baseline API latency, error rate, queue depth and execution completion measurements
- exercise database backup/restore procedure in a non-production environment
- exercise rollback to the previous Vercel deployment and previous ECS task definitions
- run hostile-execution/adversarial staging checks before enabling untrusted execution for broad public traffic
- resolve or explicitly defer the two old divergent PRs (#6 reliability/observability and #7 source-backed bank) after comparing their remaining unique changes to current main

## Go/no-go rule

Do not call the product production-certified because source code or CI is green. Launch is certified only when the exact final release SHA completes the production workflow and the P0 production/user-path checks above have recorded evidence.

If an external production credential or infrastructure input is missing, the release remains fail-closed; do not weaken the workflow to bypass it.
