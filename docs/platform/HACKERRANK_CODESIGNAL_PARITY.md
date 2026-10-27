# HackerRank / CodeSignal-class Product Parity Contract — Rigor / SkillForge

**Date:** 2026-10-27. **Source of truth:** rrahul0904/leetcode-platform.
**Scope:** ORIGINAL product capability parity, not clones of competitor UX/source/content.

Reference product docs reviewed 2026-10-27:
- https://support.hackerrank.com/articles/7917691813-introduction-to-interview
- https://support.hackerrank.com/articles/9059560249-introduction-to-hackerrank-interviews
- https://www.hackerrank.com/products/screen
- https://support.codesignal.com/hc/en-us/articles/22112130416535-Quick-Start-Guide-Assessments
- https://support.codesignal.com/hc/en-us/articles/12984563824279-Practice-Content-Overview
- https://codesignal.com/pricing/
- https://codesignal.com/technical-assessments/

## Product experiences / proof

| Capability | Learner | Candidate | Interviewer / Employer | Release proof | Status |
|---|---|---|---|---|---|
| Canonical question catalog | browse filtered published items | see assigned questions only | create/review/approve own authorized versions | cross-role, unpublished & private leak tests | existing; integration not certified |
| Monitored execution | run Python, SQL and tests | real isolated Run/Submit | inspect public/hidden results | sandbox isolation, deadline and replay tests | existing; production gate blocked |
| Guided learning | courses, tracks, AI hints, spaced review | practice only with explicit separation from hiring session | no access to personal learning evidence | learner A/B separation + consent tests | partial existing |
| Mock interviews | start personal mock, feedback | distinct from employer session | not employer-scored | owner-only persisted history; calibration | existing mock API only |
| Timed technical screening | voluntary practice simulations | authentic invitation, server clock, autosave and resume | create invite, revoke and schedule | multi-tenant invites, replay, expiry | not implemented |
| Real-world coding | repo/debug/PR exercises | solve multi-file project | collaborative review | secure reproducible workspaces, snapshots | partial PR review; not live collab |
| Live coding interview | practice paired interview | join video/audio/text and shared IDE | join, annotate, follow-up | 2+ user synchronization and recording consent | not implemented |
| AI interviewer | Socratic learning w/hints | adaptive technical probes without leaking keys | draft evidence-linked rubric | hallucination, abuse, latency, confidence testing | not implemented in hiring mode |
| Rubric/scorecards | feedback and growth areas | proportionate score visibility | human review, challenge, override | blind regrade, calibration, audit | provisional private MCQ only |
| Integrity | teach acceptable AI use | clear published assistance rules | review concrete integrity evidence | minimize intrusiveness, false-positive audit | not implemented |
| Company administration | not applicable | invited scoped access | organizations, RBAC, billing, retention | forced tenant RLS and A/B leakage matrix | not implemented |
| Reporting | skills progress/readiness | own results per policy | cohorts, skills, item metrics, exports | data provenance, ACL and deletion | partial learner only |
| Integration | export personal data | calendar/reminder by consent | ATS, SSO, public API, webhooks | signed events, least privilege & idempotency | not implemented |

Competitor capabilities are evidence from public documentation, not completed SkillForge features.
Do not conflate practice and hiring attempts; sharing personal practice data into a hiring context
requires affirmative informed user consent and independent security/permissions checks.

## Uploaded corpus readiness, as of this PR

| Track | Sets | Questions | Breakdown per assessment | Verification |
|---|---:|---:|---|---|
| Level 4 Data Engineering | 7 (Sets 3–9) | 112 | Python 2 / SQL 3 / PySpark 1 / Snowflake MCQ 10 | offline staged / review_required |
| Level 4 DevOps | 10 (Sets 1–10) | 140 | Advanced Python 2 / DevOps scenarios 2 / MCQ 10 | offline staged / review_required |
| **Total** | **17** | **252** | Both: 60 minutes, 100 marks | NOT published |

None of these uploaded sets are automatically published or employer selectable.
Interviewer-only solution guides and scoring keys are deliberately absent from this repository.
Do not deliver any candidate HTML/JSON/bundle containing solution guides, hidden tests or rubric keys.
Candidate source packages require ownership/redistribution approval and technical/editorial QA.

## Product-level first production workflow

1. Employer tenant admin signs in, verifies employer account, configures recruiting roles.
2. Reviewer approves sourced question versions and scoring contract.
3. Employer builds a 60-minute assessment and sends scoped, expiring invite.
4. Candidate verifies invitation, accepts privacy terms, configures accommodations,
   accesses only candidate-visible question versions and starts server-authoritative timer.
5. Candidate runs tested Python/SQL in isolated worker; submits written scenarios and MCQ answers.
   PySpark source material is written/scored by humans until a suitable safely isolated Spark
   execution contract is independently qualified.
6. Candidate joins an AI-assisted conversational technical interview in text mode (optional
   consent-based speech), with visible allowed-help rules and followups grounded in job skills.
7. Automated MCQs are provisional; objective sandbox tests produce bounded execution evidence;
   AI proposes criterion-level evidence with confidence and uncertainty, no hiring recommendation.
8. Human interviewer reviews/revises rubric, documents outcome; candidate gets appropriate feedback.
9. Audit, retention, correction requests, tenant isolation and revoke/rollback tested; no launch
   until exact-SHA, end-to-end two-party UAT, security and owner signoff pass.

**Never** ship with hidden keys client-side, use global hiring score thresholds without job
validation, penalize disability/accent/appearance, infer demographic traits, or make autonomous
hiring decisions. No invasive surveillance by default.

## REA success receipts required

- Spec and clean-room donor references recorded; exact code commit and staged content hashes.
- 2 employer organizations × 2 candidates with positive and negative RBAC/RLS tests.
- Expiration, multiple-tab, resubmission, browser crash/resume, idempotency/replay tests.
- Sandboxed code Run/Submit adversarial suite and actual runner receipts.
- AI transcript + rubric references attributable to actual responses; review audit.
- Accessibility, WCAG keyboard/screen reader, international time zone and latency tests.
- CI (lint/types/unit/integration/browser), SCA/SBOM, production migration, backup and restore.
- Independent approve/decline human signoff before any merge or production promotion.
