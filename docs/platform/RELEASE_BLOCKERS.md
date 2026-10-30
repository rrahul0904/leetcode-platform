# Release blockers and owner actions

As of 2026-10-29, the four-wave AWS release is **NO-GO**. The canonical gate ledger is `skillforge_four_wave_gate_status.json`; this file explains the blockers without adding a competing pass/fail state.

| Gate | Exact blocker | Required owner action / proof |
| --- | --- | --- |
| L01/L02 | No observed real employer Python and SQL SQS → EKS/gVisor run or hostile-code proof | AWS operator provisions protected staging; independent security reviewer replays valid, wrong, malicious and timeout submissions at exact SHA/image |
| L03 | AWS tenancy, identity, remote state and live app not observed | Cloud owner provides authorized staging/production account, OIDC, domain, Clerk and Secrets Manager configuration; independent endpoint/DB proof |
| L04 | 252 DE/DevOps items are privately staged, rights and technical/editorial approval pending | Rights owner confirms lawful source and independent reviewers approve first-party content and hidden cases; no private guides in repository |
| L05/L08 | No two-org/two-candidate deployed browser proof, email delivery, accommodation or accessibility acceptance | QA/product owners execute real hosted flows with independent accounts and assistive technology; record exact SHA and endpoint |
| L06 | Live model configuration and privacy abuse review absent | AI/privacy owners verify provider, consent, erasure, failures and injection tests, or disable advertised feature |
| L07 | No approved integrity workflow and appeal | Privacy/product owners either remove from launch scope via authorized gate policy or prove proportionate review and appeal |
| L09 | No production-representative PITR restore, load, alerts or rollback drill | Cloud operations owner runs and records drills on approved infrastructure |
| L10 | PR #70 draft; no independent security/content/ops/product approval or same-build promotion | Human reviewers sign exact SHA/image receipts; release owner explicitly authorizes promotion after all gates pass |

Local source checks and CI cannot satisfy these gates. No production deployment, merge or public content publication has been authorized or performed.
