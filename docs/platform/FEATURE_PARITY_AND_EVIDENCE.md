# Capability and evidence matrix

**Observed source:** PR #70 baseline `c35aee9b27d35aa2060aa93568c47f3eb29c541f`; main `2e785369d97c387932931e1954b1b715183b5784` on 2026-10-29. Local tests are source evidence only. Production proof is absent for every row below.

| Capability | Required behavior | Observed path | Runnable check | Environment / status | Failure or next action / owner |
| --- | --- | --- | --- | --- | --- |
| Learner catalog and practice | Approved published bank, Python/SQL Run and progress | `apps/web/app/question-bank`, `apps/api/src/rigor_api/execution_routes.py`, `services/*-runner` | Existing execution and catalog suites | Local / PARTIAL | Recheck approved published count and live persistence; content/QA owner pending |
| Employer organization | Self-service tenancy and roles | `employer_organization_routes.py`, migration `20261027_0022` | `test_employer_organizations.py` | Local / PARTIAL | Base organizations and membership tables lack forced RLS; security owner pending |
| Assessment content | Rights, independent review, immutable version | `employer_assessment_routes.py`, `employer_execution_fixture_routes.py` | `test_employer_assessments.py` | Local / PARTIAL | 252 staged items are not rights-approved; content owner pending |
| Python/SQL pads | Save, Run sample, final hidden Submit | `apps/web/app/assessments/page.tsx`, `assessment-coding-pads.tsx` | component tests, employer HTTP test | Local / PARTIAL | Default-off availability probe added; no live cloud run; platform owner pending |
| Private scoring | Typed fixtures and deterministic hidden comparison | `employer_code_contract.py`, `employer_code_execution_worker.py`, migration `20261029_0027` | contract tests, PostgreSQL HTTP integration | Local simulated sandbox / PARTIAL | Need real EKS/gVisor and independent malicious-case replay; security owner pending |
| AI interviewer | Consent-scoped model-backed text dialogue | `employer_ai_interview_routes.py`, `employer_interview_provider.py` | employer HTTP test with provider stub | Local / PARTIAL | Live provider/privacy review required; AI/privacy owner pending |
| AI reviewer | Advisory criterion suggestions, human override | No employer reviewer service observed | None | MISSING | Design and validate after deterministic evidence; product/QA owner pending |
| Integrity and appeal | Transparent human-reviewable evidence | No production employer workflow observed | None | MISSING | Exclude from marketing until approved; privacy owner pending |
| Live collaboration | Shared room, presence, reconnect | No employer room implementation observed | None | MISSING | Two-device proof required; product owner pending |
| AWS operations | Exact build, staging, backup, rollback, monitoring | `infra/terraform`, `infra/kubernetes`, `.github/workflows` | Terraform/source checks | Source-defined / BLOCKED | Provisioned resources and independent receipts absent; cloud owner pending |

Status vocabulary: VERIFIED means independently observed in the required environment; PARTIAL means code or local proof only; MISSING means no implementation observed; BLOCKED means external approval or resource is required. No row above is a production verification claim.
