# Technical learning consolidation

The canonical implementation target is `rrahul0904/leetcode-platform`.

This integration branch deliberately brings the compatible technical-learning slices
onto one lineage instead of creating more standalone products:

- SkillForge / Rigor: canonical question bank, practice, execution, evidence, and
  readiness platform.
- Layrs AI Tutor: adaptive Socratic coaching, tutor sessions, code/whiteboard context.
- Real-SWE Premium: production-style PR Review Lab with deterministic server grading.
- KeetKote capability: source-backed company interview preparation and candidate
  readiness coverage.
- ClankerRank capability: AI Arena prompt competition, generated-code evaluation,
  scoring, ratings, tiers, and leaderboard.
- DataForge and the earlier Elite AI / Big-Tech preparation specification remain
  product-requirement sources for the same canonical platform rather than separate
  runtimes.
- Mock interviews: persisted, candidate-owned technical interview sessions across
  Data Engineering, Python, SQL, system design, AI architecture, and staff leadership,
  with deterministic rubric evidence feeding competency mastery.
- Learning paths: candidate-facing role paths that organize canonical SkillForge
  tracks and link directly into governed practice, mock interviews, and readiness.
- Mookti learning-OS donor: a general Study Workspace for projects, deadlines,
  daily plans, focus evidence, learning notes, and spaced review that reuses the
  existing tutor, learning paths, evidence model, and release lineage.

The branch intentionally does **not** absorb unrelated or explicitly excluded learning
products. In particular, the Kinduru-inspired guided-flow branch is not merged into
this consolidation.

## Shared platform rules

Every consolidated feature should reuse the same primitives where applicable:

- authenticated SkillForge users and permissions;
- PostgreSQL and Alembic migration lineage;
- forced RLS for candidate-owned state;
- governed published question versions;
- the canonical durable execution plane and isolated runners;
- server-authoritative evaluation evidence;
- shared readiness/progress semantics;
- Next.js candidate shell and API BFF;
- fail-closed production migration/deployment checks.

This keeps reverse-engineered product ideas as capabilities inside one coherent
technical-learning system rather than accumulating disconnected clones.


## Candidate surfaces

The consolidated candidate experience now includes:

- `/question-bank` for governed published practice and Data Engineering filtering;
- `/ai-arena` for the ClankerRank-inspired prompt competition;
- `/mock-interviews` for persisted technical interview sessions and reports;
- `/learning-paths` for Data Engineering, backend, AI-platform, and data-architecture paths;
- `/progress` for evidence-backed readiness and next actions.

These surfaces share the same identity, PostgreSQL lineage, candidate evidence, and
production release boundaries. They are not separate microsites or disconnected demos.
