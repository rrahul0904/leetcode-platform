# Production release checklist

Target: the existing Vercel project `skillforge-interactive-demo` for the Next.js web app, with API and worker images deployed to ECS by the checked-in workflows. The Vercel workflow verifies the release commit and production endpoint; it also runs database migration and catalog publication steps. Do not dispatch it until the repository checks pass on the exact commit to release.

## Owner actions

1. **Repository maintainer:** push the local `codex/release-integration` branch, open a PR to `main`, and make required CI checks green. Its implementation commit is `a73cee662e7c3a19bf9ed5415a8ec243bd7c883e`; capture the final branch HEAD and merge only that reviewed release SHA. The branch currently exists only in the local checkout.
2. **GitHub/Vercel environment owner:** in the GitHub Actions `production` environment, set the customer-owned bare DNS hostname as `SKILLFORGE_PRODUCTION_HOSTNAME` and add `VERCEL_TOKEN` as a secret. Confirm the hostname is already attached to the intended Vercel project; the workflow checks current ownership and does not reassign it manually.
3. **Vercel project owner:** configure production environment values `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` (`pk_live_*`), `CLERK_SECRET_KEY` (`sk_live_*`), `RIGOR_BACKEND_ORIGIN` (HTTPS or Vercel internal service origin), and `RIGOR_DATABASE_URL` or `POSTGRES_URL` (reachable PostgreSQL URL). The release workflow derives and stores the Clerk issuer/JWKS, canonical app URL, same-origin API path, and allowed origin after validation.
4. **AWS platform owner:** configure GitHub `production` environment variables `AWS_REGION`, `ECS_CLUSTER`, `ECS_API_SERVICE`, `ECS_WORKER_SERVICE`, `ECR_API_REPOSITORY`, `ECR_WORKER_REPOSITORY`, and `AWS_DEPLOY_ROLE_ARN`. Configure that role's GitHub OIDC trust and least-privilege access to push the two ECR images and update/wait for the two ECS services.
5. **Release owner:** after merge and green exact-SHA CI, manually run `Deploy existing SkillForge production` for the approved main SHA. Verify its certification artifact records the Vercel deployment ID/URL, ECS workflow run, migration head, and canonical hostname. Retain the previous Vercel deployment and ECS task definitions for rollback.
6. **Product/tracker owner:** provide canonical tracker access, resolve the RE-292 and RE-326 collisions without changing DustByte or Sky Reach, then allocate canonical IDs for Study Workspace, Code Typing, and Typing Arcade if accepted as separate rows. Keep these rows pending until the release evidence is available.

## Release checks before dispatch

- Repository gates pass on the exact commit: frozen JS and Python installs, web lint/typecheck/tests/build, Python Ruff/Pyright/Pytest, migration cycle, IaC/workflow validation, security scans, and SBOM.
- Production Vercel settings have the required live identity, database, and backend values above; the requested domain resolves to the intended Vercel project.
- ECS OIDC role and all six ECS/ECR settings resolve to the intended production services and repositories.
- Browser, accessibility, responsive, API readiness, ownership-isolation, execution, and rollback checks have owners and evidence capture enabled.

Current state: implementation is committed locally (see `a73cee662e7c3a19bf9ed5415a8ec243bd7c883e`); no remote PR or preview exists. The web checks pass locally, while Python/security/IaC CI, authenticated browser UAT, and production certification remain outstanding. The deployment values listed above are absent from this environment.
