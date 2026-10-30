# SkillForge launch acceptance — implementation evidence ledger

**Last inspected:** 2026-10-29 · Repository: `rrahul0904/leetcode-platform` · Candidate PR #70 at baseline `c35aee9b27d35aa2060aa93568c47f3eb29c541f`.
**Release verdict:** **NO-GO** until every P0 item below has a signed, exact-SHA production evidence receipt.
The CI passing is a code-level certification, **not** proof of a deployed and safe production SaaS.

## What is implemented and independently verified in code

- Authenticated employer tenant and candidate HTTP assessment workflow, invitation acceptance, deadlines, server-side drafts, submit lock and human-only rubric scoring.
- Dedicated Python and SQL response pads, explicit question languages, draft-branch candidate Run/Submit APIs and a local simulated-sandbox integration test; plus an opt-in, separately consented AI technical interviewer. No live isolated employer execution is certified.
- Candidate transcript erasure protected at the PostgreSQL restrictive RLS boundary.
- Human-reviewed reports, tenant-scoped CSV and no autonomous hiring decisions.
- One-use HTTPS candidate invitation links encoded in URL **fragments** and scrubbed from candidate browser history after reading; manual credential entry remains available.
- AI-interview interrupted-turn recovery with a 90-second lease and candidate ownership.
- Reviewer responses cannot be accessed through the employer answer-detail API until candidate submission.
- Terraform-defined ECS/Fargate web, API and worker services, TLS, WAF and production migration checks. This infrastructure is **source-defined, not verified as provisioned**.

## P0 — hard launch blockers (all required)

| ID | Required product proof | Current verified evidence | Gate |
|---|---|---|---|
| L01 | Employer Python and SQL code **Run / Submit** with secret hidden cases, trusted comparator and immutable score receipt | Draft branch has typed fixtures, candidate Run/Submit, default-off availability fencing, trusted comparator and local simulated worker tests; a migration binds terminal rows to fixture, runtime image and result digests. No real cloud isolated run or independent security review | NO-GO |
| L02 | Real SQS → trusted controller → EKS/gVisor Python and SQL execution: escape, network, metadata, timeout, concurrency, crash and result-fencing abuse tests | Source and unit/integration contracts; **no observed production execution-plane run** | NO-GO |
| L03 | Production tenant data, OIDC/Clerk live key, HTTPS domains, secrets, monitored queues, remote Terraform state and protected AWS credentials | Terraform and container CI only; production AWS state and runtime not observed | NO-GO |
| L04 | All publicly served assessment content legally distributable and independently technical/editorial approved, with versioned confidential keys, test cases and calibrated rubrics | 252 candidate-facing items privately staged; **not approved for publication** | NO-GO |
| L05 | Full two-organization/two-candidate **live** browser UAT: real auth, invitation delivery, autosave/restart, Python+SQL run, submit, human review, privacy and tenant denial | HTTP integration and stubbed browser navigation tests; no actual multi-party deployed UAT receipt | NO-GO |
| L06 | Real provider AI config, quota/error handling, prompt-injection/privacy red team, consent and transcript deletion verified end-to-end, or disable the advertised AI feature for launch | Provider adapter exists; no live production model credentials or red-team receipt | NO-GO |
| L07 | Reviewable integrity workflow, truthful evidence provenance, candidate correction/appeal and privacy retention **if marketed** | V4 standalone demo only; no production fraud/identity detection | NO-GO unless excluded from launch |
| L08 | Email delivery / candidate onboarding, user-friendly invitation expiry/revoke, support, accessibility keyboard/screen reader and accommodation policy | Manual one-use link handoff exists; no verified transactional outbound email or complete accessibility UAT | NO-GO for public enterprise rollout |
| L09 | Point-in-time database restore, ECS/API/worker and frontend rollback, incident alerts, log audit, backup and incident-drill evidence | Infrastructure and rollbacks exist as code, no production restore/load drill evidenced | NO-GO |
| L10 | Independent security/privacy and product reviewer signoff; exact merged main commit, production deployment receipts, customer-owned domain and realistic candidate-to-employer acceptance | PR #70 remains draft; no AWS deployment; approval not recorded | NO-GO |

## Required launch proof bundle

An independent release owner must attach all of:

1. **Build:** immutable merged release SHA, passing full GitHub CI, CodeQL/Trivy, SBOM and tested image digests.
2. **Content:** rights/approval records, full question test matrix and zero candidate-visible rubric/hidden-test leakage.
3. **Real test:** exact API/web endpoints and timestamped authenticated UAT for two employers/two candidates, Python/SQL sandbox execution IDs and reviewer receipts.
4. **Security:** actual cross-tenant RLS, hostile sandbox escape attempts, protected AI consent, incident investigation and privacy erasure.
5. **Operations:** production database migration/persistence, PITR restore, rollback, health, alarms, queue/DLQ metrics and load results.
6. **Signoff:** human approve/decline decision *after* the above checks, plus documented rollback operator.

Do not convert `readyz`, a passing build, a staged question count, or a simulated HTML demo into a production-readiness claim.
Do not use Vercel, Railway or Render for product production deployment.

## Next implementation order

1. **Real employer coding evaluation vertical slice:** complete availability fencing and independently prove the draft implementation on actual AWS SQS/EKS/gVisor for Python and SQL, with hostile-code and cross-tenant negatives.
2. Provision representative **isolated AWS staging**, run complete worker and hostile code execution tests, then secure tenant UAT.
3. Wire real invitations, verified AI model, accessibility and human integrity review; complete content approval.
4. Execute backup/restore, rollback, load, independent audit and owner-controlled launch.

**Primary change tracking:** PR #70 and issue #71. This document is the release acceptance contract; do not infer launch success from historical readiness percentages or older `LAUNCH_WEEK` status documents.
