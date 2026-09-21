# SkillForge CareerOS

## Product direction

CareerOS expands SkillForge from a technical-interview question platform into a persistent job-search workspace.

The product loop is:

```text
Career profile
  -> target job
  -> resume + job description analysis
  -> evidence / gaps / fit intelligence
  -> tailored application assets
  -> tailored interview plan
  -> mock interview + scoring
  -> application follow-up
  -> outcome learning
```

The objective is not to build another generic resume generator. The durable value is the candidate context accumulated across applications and the connection between job requirements, resume evidence, SkillForge practice, interviews, and eventual outcomes.

## Product principles

1. **One candidate context** — experience, projects, skills, target roles, evidence, and preferences should be reusable across every application.
2. **Explain before generating** — fit and gap recommendations should show their evidence rather than hide behind an opaque score.
3. **Practice is connected to the job** — detected gaps and likely questions should lead into SkillForge's existing question bank and mock-interview surfaces.
4. **Human approval for career claims** — generated resumes and answers must not invent experience or credentials.
5. **Low-cost core** — deterministic analysis and retrieval should handle work that does not need a paid model call.
6. **Provider abstraction for AI** — model-backed features should be replaceable and observable rather than coupled to one LLM vendor.
7. **Application history becomes the moat** — over time CareerOS should learn which positioning, skills, preparation, and applications lead to screens, interviews, and offers.

## Wave 1 — Job intelligence foundation

Status: **implemented on `agent/careeros-wave-1`**

User flow:

1. Candidate opens `/career`.
2. Candidate enters a target role/company and pastes resume text plus a job description.
3. Authenticated API analyzes the two documents.
4. Candidate receives:
   - explainable 0–100 fit score;
   - explicit skill coverage;
   - priority-language overlap;
   - matched resume evidence;
   - missing named skills;
   - strengths and risks;
   - priority job-description keywords;
   - tailored interview questions and coaching notes.
5. Candidate can continue into the existing question bank or mock-interview workspace.

The first analyzer is intentionally deterministic. It provides a stable baseline, works without a model API key, and makes regressions testable.

### Wave 1 architecture

```text
Next.js /career
  -> career-api.ts
  -> /api/backend/api/v1/career/jobs/analyze
  -> FastAPI CareerOS router
  -> deterministic evidence analyzer
  -> CareerJobAnalysis
  -> fit/gap/interview UI
```

Authentication continues to use the existing SkillForge candidate identity path. Non-candidate roles cannot invoke CareerOS analysis.

## Wave 2 — Persistent application workspace

Add durable candidate-scoped entities:

- `career_documents`
  - resume source, parsed text, checksum, version, extraction state
- `career_jobs`
  - company, title, source URL, canonical job description, status
- `career_job_analyses`
  - scoring version, matched/missing evidence, score components, generated timestamp
- `career_applications`
  - planned/applied/screen/interview/offer/rejected/withdrawn status and timestamps
- `career_artifacts`
  - tailored resume, cover letter, recruiter note, follow-up, interview brief
- `career_interview_sessions`
  - target job, question plan, transcript/evidence references, scores

Requirements:

- PostgreSQL row ownership / RLS consistent with the existing production schema.
- Audit events for create/update/generate/export actions.
- Analysis versioning so score changes are explainable after algorithms evolve.
- Resume upload through the existing candidate file upload infrastructure.
- PDF/DOCX text extraction in a bounded worker path; never parse large documents in the request process.

## Wave 3 — AI application copilot

Introduce a provider-independent generation service with structured outputs.

Capabilities:

- extract candidate evidence into a normalized career profile;
- map each JD requirement to exact resume evidence;
- generate resume suggestions without inventing facts;
- create role-specific bullet rewrites for user approval;
- generate cover letter, recruiter message, and follow-up drafts;
- company/recruiter research with source citations when public web retrieval is enabled;
- save prompts, provider/model, latency, token cost, and output version for observability.

Guardrails:

- every generated career claim must point to candidate-provided evidence;
- unsupported claims are blocked or labeled as a question for the candidate;
- generated assets remain drafts until the candidate accepts them;
- secrets and private candidate documents are never included in logs.

## Wave 4 — Interview Room

Connect CareerOS directly to SkillForge's learning engine.

For each target job:

- construct a role-specific interview blueprint;
- retrieve relevant questions from the existing SkillForge bank;
- mix technical, behavioral, system-design, and resume-deep-dive questions;
- run text and later voice mock interviews;
- score answers against question rubrics and candidate evidence;
- generate follow-up questions dynamically;
- convert weak areas into a practice queue;
- show improvement over repeated sessions.

## Wave 5 — Job Search Agent

Add a candidate-controlled application tracker and scheduled actions:

```text
Saved -> Tailored -> Applied -> Screen -> Interview -> Offer
                     |            |
                     + follow-up  + interview plan
```

Capabilities:

- application dashboard and timeline;
- follow-up reminders;
- interview-date preparation plans;
- reusable recruiter/contact context;
- outcome analytics by role, company type, resume version, and fit score;
- optional job discovery and monitoring through explicit integrations.

The agent should prepare and recommend actions. Any external application, email, or account mutation should remain explicit and user-approved.

## Wave 6 — Portfolio identity and monetization

Potential product surfaces:

- resume-to-portfolio publishing;
- private/public career profile;
- shareable project and evidence pages;
- interview readiness reports;
- annual career progress review.

Suggested commercial model:

- **Free:** career profile, limited job analyses, basic fit/gap report, sample interview pack.
- **Job Pack:** one-time paid unlock for tailored application assets and a full target-job interview plan.
- **CareerOS Pro:** recurring application tracking, higher analysis limits, full mock interviews, longitudinal coaching, and portfolio publishing.

Avoid putting basic candidate data behind an export trap. Charge for repeated intelligence, generation, interview coaching, and automation.

## Success metrics

The north-star metric should not be resume generations. Track movement through the job-search funnel:

- analysis -> tailored application conversion;
- application -> recruiter screen rate;
- screen -> interview rate;
- interview -> next-round rate;
- offer rate;
- mock-interview completion and score improvement;
- weekly active candidates with at least one active application;
- paid conversion after a candidate receives useful free fit intelligence.

## Immediate engineering backlog

1. Ship and validate Wave 1 behind the existing SkillForge authentication boundary.
2. Add PostgreSQL migrations and candidate-scoped persistence for jobs/analyses.
3. Connect resume uploads to text extraction and document versioning.
4. Add analysis history and compare-two-resume versions.
5. Introduce a structured LLM provider adapter and evidence-bound resume tailoring.
6. Retrieve SkillForge questions by analysis gaps and create a job-specific practice plan.
7. Add application states and follow-up dates.
8. Add observability for analysis latency, failures, model cost, and conversion events.
