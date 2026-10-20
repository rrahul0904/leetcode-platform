# SkillForge V1 — implementation delivery project

**Canonical GitHub project:** [#55](https://github.com/rrahul0904/leetcode-platform/issues/55)  
**Repository:** \`rrahul0904/leetcode-platform\` (no new repository).  
**Deployment target:** Vercel \`skillforge-platform\` / \`prj_cKifcPIyHvvuL6EZAgvUC8mpbQEq\`.  
**Release posture:** NOT CERTIFIED. Never infer readiness from source files, CI green, screenshots or Vercel READY alone.

## Product boundary (V1)

One real user's path must work: **sign up → sign in → browse approved questions → run Python and SQL → submit → see scored feedback → view durable attempts and progress → sign out and sign in again**.

One real admin's path must work: **sign in with admin role → import/review/approve/publish or unpublish first-party content → inspect catalog state**. Candidates cannot access admin APIs, each other's records or hidden scoring material.

**Out of release-critical scope:** donor research/REA intake, Trace Lab (#53), Blitz Arena (#52), new interview voices (#49), additional CareerOS scope (#38), and UX polish not affecting the critical path. Do not delete that work; queue it until the V1 release is certified. Study Workspace, Code Typing and Typing Arcade may remain local-only if clearly labelled and tested; do not represent local storage as cloud persistence.

## Source-of-truth and integration order

- Verified integration base \`main\` was observed at \`2e785369d97c387932931e1954b1b715183b5784\`; **re-read HEAD** for every later merge, do not treat this SHA as permanently current.
- **#51** is the canonical hosted reconstruction branch. **#48** remains superseded only after equivalent-diff/PR disposition. Preserve main's health-probe BFF fix and auth guarantees.
- **#54** adds exact Vercel deployment/commit metadata verification and passed exact-head GitHub CI, Python evidence, security and migration preflight on \`458f35a1bbf6890e18cdd0987945aeee3b2733f4\`. It is stacked onto #51; merging either requires reviewed exact-head checks. No live Preview acceptance is claimed.
- Treat \`skillforge-reconstruction\` and \`skillforge-interactive-demo\` as noncanonical deployment targets; never promote those in place of \`skillforge-platform\`.
- Architecture for the V1 release: Vercel Next.js web / FastAPI API, Clerk identity, managed Postgres, Vercel Sandbox. The alternate EKS plane stays explicitly fail-closed until separately certified.

## Milestones, acceptance and dependency chain

| Stage and issue | Implementable work | Proof required to close | Dependency / disposition |
|---|---|---|---|
| **P0 [#56](https://github.com/rrahul0904/leetcode-platform/issues/56)** Contract + release intake | Canonical plan, fail-closed machine-readable release state, exact-SHA gating, CI schema validation and tests; reconcile outstanding PRs without assuming merged = launched | Code/tests on exact reviewed SHA; no dishonest \`ready\` status | Active; this implementation PR |
| **P1 [#57](https://github.com/rrahul0904/leetcode-platform/issues/57)** Hosted Preview | Bring #51/#54 together, get exact source deployed to \`skillforge-platform\`, inspect FastAPI bundle and missing \`question-bank-manifest.json\` fix, stop redundant deployment builds where possible | Vercel metadata exact project/SHA/ID + protected \`/\`, \`/sign-in\`, \`/api/backend/livez\`, \`/api/backend/readyz\` HTTP 200 and unauthed denial + logs | P0; provider build-rate quota / Preview bypass |
| **P2 [#58](https://github.com/rrahul0904/leetcode-platform/issues/58)** Auth and durable state | Clerk account → API identity reconcile, verify Neon DB migration head, forced RLS, persisted candidate state | Real two-account login/logout/relogin; A/B ownership denial, role-denial and database persistence receipts | P1; valid Clerk/DB configuration |
| **P3 [#59](https://github.com/rrahul0904/leetcode-platform/issues/59)** Content + execution | Review/publish only licensed first-party 50-pack corpus; hosted Python/SQL Run+Submit, server adjudication, persistent attempts, sandbox security | At least one real runnable Python and SQL problem, verified output, timeout/network/file/tenant isolation and hidden-test secrecy | P1–P2; hosted sandbox |
| **P4 [#60](https://github.com/rrahul0904/leetcode-platform/issues/60)** Candidate/admin UAT | Real browser end-to-end (candidate and admin), desktop/mobile, keyboard, accessible focus, empty/error/retry | Exact-SHA Playwright/browser receipts, 2 accounts, role isolation, persisted attempts and no blocking console errors | P2–P3 |
| **P5 [#61](https://github.com/rrahul0904/leetcode-platform/issues/61)** Production | Production domain & live Clerk, backup/restore and migration; stage tested production build without alias; security, rollback, observability and distinct promotion | Real safe backup/restore evidence; exact production staged deployment; reviewer approved same-build promotion; authenticated public-domain smoke and rollback record | P0–P4 certified, protected environment owner + reviewer |

### Execution order and stop conditions

1. Lock V1 scope. Record new REA references as backlog-only. No feature branch can silently change launch criteria.
2. Integrate #51 after exact branch-head CI, security, migrations and diff check. Follow with #54's Preview proof. Never short-circuit missing provider identity.
3. Request provider build capacity if rate-limited. A previous READY deployment cannot stand in for the current SHA.
4. Run hosted Preview health, identity, database and execution acceptance. A failed acceptance produces one specific reproducer, owner, PR and rerun.
5. Perform two-account security and admin/candidate workflow UAT on the same exact release candidate.
6. Prepare a state-backed production migration plan and independently verified backup/restore record; do not mutate the customer database during research or Preview.
7. Stage production \`--skip-domain\`, independently certify staged exact build, obtain approval, promote **the same build**, then run post-deploy acceptance/monitoring/rollback review.

Any critical failure reopens its issue and blocks all dependent gates. Do not count issues/PRs/commits as product completion.

## Automated truth contract (implemented in P0)

- Record: [skillforge_v1_gate_status.json](skillforge_v1_gate_status.json) covers 15 ordered gates.
- CLI: \`python scripts/skillforge_v1_release_gate.py --validate\` checks schema/targets/dependency order, \`--report\` emits truthful blocked/verified counts, \`--assert-pre-release\` and \`--assert-complete\` fail until all corresponding gates are documented.
- A \`verified\` gate requires a **40-character SHA equal to the release SHA**, an exact GitHub Actions run URL, UTC observation time and reviewer. Deployment gates also require a \`dpl_...\` identifier. A blocked gate requires a reason. Later gates cannot pass if earlier gates are blocked.
- **Important limitation:** the CLI validates claim integrity; it does **not** authenticate Vercel or GitHub evidence contents. #54 and the independent release reviewer must separately verify actual remote deployments and runtime receipts. Passing the CLI permits further review, not an automatic production promotion.
- CI validates the blocked baseline schema without requiring external credentials. \`--assert-complete\` must currently fail. No fake success fixture belongs in the authoritative file.

## Current observed blockers (October 19, 2026)

- Canonical Vercel Preview latest observed deployment was not current PR #51 head; the historical hosted API reported missing question-bank manifest; source fix has not been live-proven.
- Vercel currently reports build-rate-limit check failures for newer pushes.
- Canonical project production env lacks configured Clerk live keys; no proven customer-owned production hostname or approved backup restore evidence.
- No hosted two-account/RLS, Python and SQL sandbox, candidate/admin full journey, independent staging and rollback certification exists yet.
- Docs in \`main\` still include a July implementation ledger and October 2 release ledger; historical evidence must not overwrite current truth.

## Evidence format and owner actions

Evidence should be a redacted receipt: deployment ID/project/URL/SHA; GitHub run URL; checked path and response class; negative security assertion; UTC timestamp; reviewer handle. Keep auth cookies, tokens, env values, user data and sandbox private outputs out of issues/artifacts.

**User/provider-owner actions (only when ready for each gate):** authorize available Vercel build capacity and Preview bypass; configure Clerk and database in the protected Preview/Production environments; confirm customer-owned hostname; provide trustworthy backup/restore proof; explicitly approve migration/promotion. Never paste credentials into ChatGPT or GitHub issues.

**Release implementer:** deliver code, tests, PR, exact SHA receipts and remaining blockers, continuously update this issue matrix as proofs change. **Independent reviewer:** sign off release-critical evidence and verify that new code hasn't bypassed safety boundaries.

**Definition of Done:** every 15-gate contract item is truthfully verified, the real public product flow is proven, production promotion is approved, and post-promotion monitoring is clean. Until then: **NOT COMPLETE**.
