# Rigor / SkillForge — Dual-Mode Learner + AI Interview Platform
## REA implementation contract (initial vertical, 2026-10-26)

**Canonical product:** \`rrahul0904/leetcode-platform\`. This is a two-sided original platform for technical learning AND employer-initiated structured interviews/assessments. HackerRank and CodeSignal are product-pattern references, not sources of copied code, questions, data, design or private behavior. **The existing SkillForge V1 release gates in issue #55 remain independent and BLOCKED.** This document does not authorize production deployment.

## 1. Product boundaries

| Learner mode | Interview/organization mode |
|---|---|
| Learn concepts and role tracks | Set up employer organization and interviewer roles |
| Practice published questions with hints | Create review-gated assessment from approved content |
| Run Python/SQL against an isolated evaluator | Invite candidates using expiring, scoped, single-use links |
| Mock AI conversation with transparent practice feedback | Host timed technical assessments and structured AI interview conversation |
| Track proficiency, attempts and remediation | Assess against rubrics, evidence, reviewer overrides and audit logs |
| Control profile, accessibility and privacy settings | Compare candidates using job-relevant competencies and independent human decisions |

The same source version, identity, candidate-owned evidence model and execution plane must be reused; employers must not see a learner's personal practice history without explicit consent. Recruiting records must not be used to train AI models by default.

## 2. Assessment corpus — first real user-owned source

Seven paired DOCX candidate papers and solution guides: Sets 3–9, 112 questions in total.
Per set: **60 minutes / 100 marks / Level 4 Senior–Lead Data Engineering**.

| Section | Format | Count per set | Marks |
|---|---|---:|---:|
| Python | written/code reasoning | 2 | 20 |
| SQL | written/code reasoning | 3 | 25 |
| PySpark | written/architecture | 1 | 15 |
| Snowflake | single-answer MCQ | 10 | 40 |

This is a **staging source**, not a published commercial question bank. Each DOCX is user-provided and is processed offline. The source files, full questions and complete solution guides are intentionally NOT committed to the public repository. Before any publication: establish ownership/redistribution rights, item editorial and technical review, content-version checksums, real executable fixtures for any claimed coding problem, accessibility review, and an independent security review. The CLI produces \`candidate_review_only\` and \`private_interviewer_only\` in different folders. Do not place either folder beneath Next.js \`public/\`, commit them to the public repository, or serve the private one via candidate APIs.

**Imported format:** IDs \`l4-de-s3-q01\` through \`l4-de-s9-q16\`, source digests, questions, options, points, recommended timing, publication_state=review_required. Privileged solution artifact contains keyed Snowflake answers and interview reference guide with its own digest. Source text must be reviewed before any learner, public or employer use.

### Reproduction with locally provided documents

\`\`\`bash
python scripts/import_level4_interviews.py \
  --input-dir /path/to/private/input-docx \
  --output-dir /path/to/private/staging
python -m unittest -v tests/test_level4_interview_import.py
\`\`\`

Use a private location outside the tracked git checkout and outside a served web directory. The import does not modify PostgreSQL, register an assessment, invite anyone, call an AI model or publish content.

## 3. Canonical domain model (target)

- **Organization**: tenant, ownership, billing, retention, DPA and role policy.
- **OrganizationMember**: org_admin, recruiter, interviewer, reviewer; scoped role grants only.
- **Competency / AssessmentTemplate**: role-specific dimensions, timing, weighted sections, fairness/accommodation settings.
- **AssessmentVersion**: immutable content snapshot + checksum, independently approved state; privileged rubric in separate datastore/ACL.
- **AssessmentInvitation**: candidate, scoped token digest, expiry, single-use policy, accommodation record, consent notices.
- **InterviewSession**: org_id, candidate_id, assessment_version_id, mode, started_at, deadline, submitted_at, append-only lifecycle events.
- **Response / ExecutionEvidence**: drafts, final code/SQL, test results, output digests and server-authoritative execution provenance.
- **AIInterviewTurn**: transcript, question objective, prompt-policy version, citations to allowed candidate-visible evidence, model/version, latency, confidence/uncertainty and escalation.
- **RubricScore**: evidence-backed criterion scores, deterministic grading vs provisional AI suggestion separated.
- **HumanReview / Decision**: independent rubric review, override with reason, candidate correction/appeal, decision accountable to humans.
- **AuditEvent / Retention**: append-only subject, action, scope, exact version, timestamp; enforce tenant isolation and erasure policies.

**Isolation:** current Postgres forced RLS cannot alone certify employer multi-tenancy. New tables must have tenant-aware forced RLS; check independent organization A/B and candidate A/B cross-visibility, admin denial, invited candidate scope and accessible solution-key paths. All solutions, reference code and hidden test fixtures must remain in privileged storage on server side, never in client bundles, model prompts, candidate JSON or browser logs.

## 4. AI interviewer behavior (target)

A configured interviewer asks one question at a time, listens to speech or accepts typed answers (text must remain fully supported), requests clarifying followups grounded in an approved competency and a candidate's prior answer, and produces an **evidence-linked draft rubric**, not an employment recommendation. The model must never receive private answer keys for candidate-facing tutoring or hints. The interviewer should acknowledge uncertainty rather than bluffing, honor accommodations, support handoff/retry and log model and policy versions. Recording must be opt-in with jurisdiction-aware notice, retention controls, transcript access restrictions and deletion rights.

Fairness and reliability: evaluate job-related skills only. No emotion, facial expressions, accent, demographics, disability inference or personality/character prediction. Treat AI scoring as advisory; final hiring determinations require human review, with appeal/correction access. Proctoring and invasive tracking are **not** default requirements.

## 5. REA release stages / implementation dependencies

| Gate | Implementation | Required proof | Initial state |
|---|---|---|---|
| R0 | Source provenance and rights | Input checksums, owner permission, review state | LOCAL IMPORT WORKING; rights unresolved |
| R1 | Private assessment content staging | All 7 sets / 112 items; no answer key in candidate artifact | LOCAL TESTS PASS |
| R2 | API and database migrations | Tenant-aware forced RLS, immutable versions and audit | NOT IMPLEMENTED |
| R3 | Author/reviewer admin UI | Build, approve, publish, revoke; negative RBAC | NOT IMPLEMENTED |
| R4 | Interview invitations and timed sessions | Expiry, replay, login, resume, persistence, accommodations | NOT IMPLEMENTED |
| R5 | Safe code execution / scoring | Hosted Python/SQL and deterministic hidden tests; PySpark separately gated | EXISTING PLATFORM INCOMPLETE |
| R6 | AI interviewer | Controlled turns, consent, transcript, rubric evidence, independent calibration | NOT IMPLEMENTED |
| R7 | Results, review and reporting | Reviewer workflow, appeals, evidence and cross-tenant tests | NOT IMPLEMENTED |
| R8 | End-to-end and production | Exact SHA, Playwright UAT, sandbox abuse suite, restore, rollback, owner approval | BLOCKED |

The deterministic MCQ scorer is **provisional only** and awaits six written answer reviews (60 marks); do not show an overall 100-point result as final. No evaluation results or candidate employment decisions are produced by the importer.

## 6. Implementation order (avoid disconnected products)

1. Protect the existing SkillForge V1 source and complete #55 gates separately.
2. Add a private admin-reviewed assessment-version store and tenant RLS; migrate seven source-derived sets only after rights/QA.
3. Build organizations and interview invitations with auditable session state and time-limit enforcement on the server.
4. Reuse the existing question-bank and sandbox for run/submit; distinguish executable Python/SQL from written PySpark responses.
5. Integrate the AI interviewer and optional voice with clear model privacy boundaries; validate rubric calibration against independent human reviewers.
6. Deliver organization dashboard, evidence reports, consent/accessibility controls and release QA.

### Definition of DONE

A real company admin can create and approve a lawful assessment, invite a real candidate, candidate completes the timed assessment with isolated code execution and AI interview followups, results persist, two tenant isolation checks fail closed, human reviewers can correct/adjudicate scores, candidate receives appropriately scoped feedback, and rollback/recovery plus security/accessibility and exact-SHA production evidence have been independently verified. A green build or a local fixture is not a production certificate.
