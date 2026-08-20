# SkillForge AI

SkillForge AI is the production-oriented evolution of the interview-preparation platform in this repository. The `skillforge-ai/` subtree implements the Supabase + pgvector + FastAPI architecture requested in the August 20, 2026 build contract while preserving the existing Rigor platform work.

## Current branch

Development branch: `feature/skillforge-ai-supabase-demo`

This branch is the current source of truth for the SkillForge build. It is not production-ready yet, but the implementation has moved beyond a static UI mock.

## What is checked in now

### Frontend

- Next.js 16 / React 19 / TypeScript / Tailwind application.
- Public landing, topics, pricing, privacy, terms, login and signup routes.
- Supabase email/password authentication UI.
- Next.js 16 `proxy.ts` route protection for authenticated workspace routes when Supabase is configured.
- Working multi-view interview workspace: dashboard, question bank, Python lab, SQL lab, MCQ, enterprise scenarios, semantic search, progress, learning paths, bookmarks and content operations.
- Monaco code editor with local draft persistence.
- Python and SQL Run/Submit actions call FastAPI instead of using timer-generated success messages.
- Enterprise scenario AI review calls the `ai-explanation` Edge Function instead of fabricating a score.
- Semantic search calls the Supabase Edge Function and surfaces the actual executed retrieval mode.
- UI wording distinguishes the 24,800-record normalized corpus from the smaller frontend demo seed. It no longer claims that all records are already embedded or loaded into the browser.

### Supabase

- Postgres schema for profiles, topics, subtopics, questions, solutions, choices, tags, attempts, bookmarks, progress, learning paths, AI interactions, embeddings and import jobs.
- RLS for user-owned and content-administration data.
- Auth-user profile bootstrap trigger.
- Full-text search indexes.
- pgvector 1536-dimensional embeddings table with HNSW cosine index.
- Hybrid search RPC and keyword-only fallback RPC.
- Private `question-imports` and `generated-exports` Storage buckets with policies.
- Edge Functions:
  - `generate-embedding`
  - `semantic-search`
  - `ai-hint`
  - `ai-explanation`
  - `admin-import-webhook`
- Semantic search generates query embeddings itself when an OpenAI-compatible provider is configured and falls back to Postgres full-text search when embeddings are unavailable.

### FastAPI

- `/health`
- `/runner/python` — constrained local demo execution only; **not a production sandbox**.
- `/runner/sql` — real seeded read-only SQLite execution for local demo verification.
- `/imports/validate`
- `/imports/process` contract (worker integration still required)
- `/exports/json`
- `/exports/csv`
- `/exports/pdf`
- `/ai/batch-generate`
- `/ai/batch-embed`
- OpenAI-compatible AI provider configuration through environment variables.

### Infrastructure

- Frontend and backend Dockerfiles.
- Docker Compose starter with Redis.
- Supabase local development configuration.
- GitHub Actions build/syntax workflow for the SkillForge subtree.
- AWS architecture notes for a production path.

## Source corpus represented by the current normalization

- 24,800 unique question/scenario records.
- 24,800 matched solutions.
- 22 banks.
- 2,000 Python coding questions.
- 3,000 SQL coding questions.
- 1,800 enterprise data-engineering scenarios, including 1,090 code-linked scenarios.

The complete corpus is intentionally not embedded in the Next.js bundle. It should be imported into governed Postgres/Supabase tables from the normalized source artifacts. Source-backed records that require publishing-rights review must remain in draft/review status until those rights are resolved.

## Local startup

```bash
cd skillforge-ai
supabase start
cd infra
docker compose up --build
```

Or run services independently:

```bash
cd skillforge-ai/frontend
cp .env.example .env.local
npm install
npm run dev
```

```bash
cd skillforge-ai/backend
cp .env.example .env
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

For Supabase Edge Functions, configure the AI secrets described in `supabase/.env.example`.

## Security boundary

The FastAPI `/runner/python` endpoint is a constrained **local demo endpoint**. It executes inside the API process and therefore is not acceptable for untrusted production candidate execution.

Production candidate code must run in separately isolated runner workloads and must never execute in:

- the Next.js web container;
- the normal FastAPI application container;
- Supabase/Postgres/RDS;
- mobile/client devices.

## Still required before production readiness

- Import the complete normalized corpus into Supabase with provenance and review-state preservation.
- Generate and verify embedding coverage for approved records.
- Replace remaining demo-only question-browser/progress/bookmark state with live Supabase queries and mutations.
- Add question detail routes that can open any Supabase search hit, not only the checked-in demo seed.
- Connect import processing to a durable Redis worker.
- Add provider adapters beyond the current OpenAI-compatible contract (Anthropic, Gemini, Bedrock, Ollama and others).
- Build production-grade isolated Python/SQL execution infrastructure.
- Add production AWS IaC, secrets, load-balancing, observability and release gates.
- Verify GitHub CI green on the latest branch head and add browser E2E tests.
