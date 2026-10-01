# Mookti learning-OS reverse engineering

Verified: 2026-09-21  
Source product: https://mookti.com/  
Implementation target: `rrahul0904/leetcode-platform`  
Integration model: clean-room capability donor, not a separate runtime.

## Product thesis

Mookti is best understood as a student learning operating system rather than a single
AI tutor. The public product joins five loops that are usually separate:

1. organize courses/projects and outcomes;
2. turn deadlines into daily study work;
3. keep notes, readings, uploads, recordings, and annotations close to that work;
4. practice retrieval through quizzes and spaced-repetition flashcards;
5. use an AI tutor that teaches with hints, grounding, and an evolving view of mastery.

The free workspace is the acquisition and retention wedge. AI usage is metered through
credits and differentiated model access.

## Publicly observed capability map

| Capability | Public behavior | SkillForge reuse / clean-room response |
| --- | --- | --- |
| Project planning | Groves organize Trees; Trees hold goals, tasks, materials, deadlines, and reflection | Recreate the behavior with generic Study Projects and outcomes; do not copy naming or UI |
| Daily plans | Study plans incorporate deadlines, availability, and progress; user reviews before saving | Current donor slice builds a deterministic 90-minute plan from incomplete due work |
| AI tutor | “Ellen” teaches rather than simply completing work; hints and correction precede answer dumping | Reuse the existing SkillForge Socratic tutor and private-evaluation leakage boundary |
| Notes | Notebooks, typed/drawn notes, links, tags, attachments, export | Current donor slice adds local learning-log notes; rich notes remain pending |
| Flashcards | Generated or manual cards use a 1–5 spaced-review flow described as SM-2 | Current donor slice implements a deterministic SM-2-style scheduler and due queue |
| Quizzes | Generate quizzes from learning materials | Reuse governed question/practice primitives; general document-derived quiz generation remains pending |
| Focus | Focus/Pomodoro time is recorded against study work | Current donor slice records 25-minute focus blocks against a project |
| Course ingestion | Syllabus and learning materials can become deadlines, plans, study aids | Pending clean-room ingestion/transcription pipeline |
| Calendar/tasks | Google Calendar/Tasks integration with bidirectional sync | Pending OAuth + sync cursors + conflict handling |
| Grounded study | Tutor cites source passages from the learner’s materials and licensed library | Reuse pgvector foundation; document chunking/citations remain pending |
| Offline | Notes, tasks, calendar, flashcards, quizzes, downloaded readings work offline | Current donor slice persists browser-local state; robust sync/offline conflict handling remains pending |
| Mobile | iPhone/iPad/Mac and Android apps; iPad drawing/handwriting | Existing SkillForge mobile shell can host a later study workspace; drawing/annotation remains pending |
| Billing | Free workspace plus paid AI tiers, credit allowances, and top-ups | Reuse SkillForge SaaS billing foundation; a model-cost credit ledger remains pending |

## Current public pricing snapshot

The website and current terms were checked on 2026-09-21.

- Free: $0, core workspace plus 30 AI credits every 30 days.
- Basic: $5/month, 100 credits, Gemini-class model access and generated study aids.
- Plus: $20/month, 440 credits and higher-tier model access.
- Pro: $50/month, 1,150 credits and highest-tier model access.
- Credit top-up: $12 for 250 credits that do not expire.
- Annual billing advertises roughly 20% savings.
- A fixed-term Semester Pass advertises roughly 10% savings.
- Current website/terms describe a 14-day Plus trial; older help pages may still contain stale trial language.

Do not copy provider/model marketing literally into SkillForge pricing. The useful pattern is
a free durable workspace plus auditable AI-credit consumption.

## Public architecture clues

Mookti’s privacy documentation publicly identifies several external processors. These
are clues to system boundaries, not evidence of private implementation details:

- Firebase for authentication/database services;
- Vercel for hosting/CDN;
- Stripe and Apple in-app purchases for payments;
- Anthropic, Google, and OpenAI for AI model processing;
- Voyage AI for embeddings;
- PostHog plus Vercel analytics for product telemetry;
- Sentry for error monitoring/session replay;
- Google Calendar and Google Tasks OAuth for synchronization.

SkillForge should not clone that stack. Its existing Next.js/FastAPI/PostgreSQL/pgvector,
RLS, mobile shell, tutor sessions, evidence model, and release controls are already the
stronger shared foundation.

## Core data model for parity

A full clean-room implementation should converge on these domain records:

- StudyProject, Outcome, Task, StudyBlock, FocusSession;
- Note, Notebook, Tag, Asset, Annotation, Transcript;
- FlashcardDeck, Flashcard, ReviewEvent;
- Quiz, QuizAttempt;
- StudyPlan, PlanBlock, LearningPath, PathStep;
- TutorSession, TutorEvent, SkillMastery, Citation, SourceChunk;
- CalendarConnection, SyncCursor, ExternalEventMapping;
- Subscription, CreditLedgerEntry, ModelUsage;
- Consent and analytics preferences.

Candidate-owned records should use the same forced-RLS ownership model already used by
SkillForge. AI-generated mastery changes should continue to require evidence rather than
ordinary chat text.

## Learning loop to preserve

```text
material / syllabus
      ↓
study project → tasks + deadlines → daily plan
      ↓                              ↓
notes / source chunks ← focus session → practice
      ↓                              ↓
citations ← Socratic tutor ← evidence/mastery
      ↓                              ↓
flashcards + quizzes ← spaced review / replanning
```

This feedback loop matters more than pixel-level imitation.

## Monetization and go-to-market

The product monetizes AI rather than basic organization:

- durable core features stay useful on free;
- paid tiers increase monthly credits and model quality/choice;
- top-ups monetize bursty exam-period demand without forcing an upgrade;
- annual and semester-duration offers match student purchasing cycles;
- public campus-ambassador material offers recurring referral commission;
- the supplied URL includes Reddit campaign attribution parameters, indicating paid/social
  acquisition measurement is part of the funnel.

For SkillForge, the reusable commercial idea is “free evidence-backed workspace, paid
AI acceleration,” with transparent cost/credit accounting.

## Clean-room implementation status on this branch

Implemented:

- `/study-workspace` route;
- Study Project/outcome creation;
- task/deadline capture;
- deterministic due-date daily planning;
- per-project focus-minute evidence;
- learning-log notes;
- flashcard creation;
- SM-2-style 1–5 review scheduling and due queue;
- local persistence suitable for a first offline-capable browser slice;
- domain tests plus an end-to-end component interaction test.

Inherited rather than duplicated:

- identity and authorization;
- adaptive AI tutor;
- learning paths;
- question bank/practice;
- candidate progress/evidence;
- web BFF and release controls;
- mobile application shell;
- PostgreSQL/pgvector foundation.

Explicitly pending before product parity:

1. server-side Study Workspace persistence and forced RLS;
2. PDF/Word/slides/image/audio/video ingestion;
3. lecture transcription;
4. source chunking, embeddings, and passage citations for general study documents;
5. rich notebook editor, wiki links, tags, drawing, PDF annotation, and export;
6. generated quizzes/study guides from learner materials;
7. Google Calendar/Tasks OAuth, bidirectional incremental sync, conflict policy;
8. robust offline-first sync across devices;
9. subscription/model credit ledger and top-up flows;
10. mobile study-workspace screens and tablet handwriting;
11. accessibility, browser E2E, load/security testing, and hosted exact-SHA verification.

## Sources checked

- https://mookti.com/
- https://docs.mookti.com/
- https://mookti.com/privacy
- https://mookti.com/terms
- https://mookti.com/campus-ambassador
- Apple App Store listing for Mookti
- Google Play listing for Mookti

Only publicly observable behavior and public policies were used. No source code,
proprietary assets, or private product data were accessed or copied.
