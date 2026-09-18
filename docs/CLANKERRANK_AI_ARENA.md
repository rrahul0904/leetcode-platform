# ClankerRank → SkillForge AI Arena

## Purpose

This slice adapts the public product pattern reverse engineered in
`rrahul0904/clanker-arena` into the canonical SkillForge/Rigor platform.

The integration is intentionally architectural rather than a second standalone stack.
SkillForge remains the system of record for identity, published questions, practice
sessions, code execution, hidden-test evidence, progress, and deployment.

## Product flow

1. A candidate selects an existing published Python challenge that has a deterministic
   hidden-test contract.
2. The candidate writes a natural-language instruction.
3. The AI Arena generator receives only public problem context, public examples/tests,
   starter code, and the candidate instruction.
4. Generated Python is persisted against the exact published question version.
5. The browser submits that generated source unchanged through the existing SkillForge
   durable execution API.
6. SkillForge's existing isolated execution plane evaluates public and hidden tests.
7. The Arena finalizer reads the persisted submission result and evaluation. It never
   accepts hidden-test counts, code-quality scores, or runtime values from the browser.
8. The server computes the Arena score, applies only positive demonstrated rating
   improvement, persists the result, and updates the leaderboard profile.

## Score

The documented Arena score is intentionally explicit rather than pretending to
reproduce a private upstream formula:

- correctness: 70 points
- runtime performance: 15 points
- code-quality evidence: 10 points
- prompt efficiency: 5 points

Ratings reward improvement over the candidate's prior best result for the exact
question version. A first score of at least 70 receives a bounded first-solve bonus.
Repeating an equal score does not increase rating.

Tiers are Bronze, Silver, Gold, Platinum, and Diamond.

## Trust boundaries

- Hidden test bodies never enter the generation request or candidate browser.
- The generator uses the already-configured SkillForge AI adapter. When the configured
  provider is unavailable, the API returns a clearly labeled deterministic starter-code
  fallback instead of claiming model generation succeeded.
- Generated source must match the subsequently submitted source exactly.
- Candidate code is not executed inside the Arena route. It reuses SkillForge's existing
  durable execution/sandbox path.
- Arena rate limits, generations, and results are candidate-owned with forced PostgreSQL RLS; leaderboard profile reads expose only the public rating fields.
- Leaderboard profiles expose only display name, rating/tier, solved count, and
  submission count.
- Finalization is tied to persisted SkillForge submission/evaluation rows.

## Data model

Alembic revision `20260918_0021` adds:

- `ai_arena_profiles`
- `ai_arena_rate_limits`
- `ai_arena_generations`
- `ai_arena_results`

The revision follows the consolidated migration chain:

`20260911_0019 tutor → 20260914_0020 PR review → 20260918_0021 AI Arena`.

## API

- `GET /api/v1/arena/challenges`
- `POST /api/v1/arena/generate`
- `POST /api/v1/arena/finalize`
- `GET /api/v1/arena/me`
- `GET /api/v1/arena/leaderboard`

The candidate UI is available at `/ai-arena`.

## What was deliberately not duplicated

The standalone reverse-engineered prototype had its own persistence, auth, generator,
and judge deployment boundaries. Those are not copied into SkillForge because the
canonical platform already has stronger equivalents. In particular, the Arena does not
create a parallel Supabase identity store or a second Judge0 execution stack.

This work reproduces product behavior and independently documented mechanics. It does
not copy private upstream implementation, proprietary hidden tests, private APIs,
branding, or an undisclosed rating formula.
