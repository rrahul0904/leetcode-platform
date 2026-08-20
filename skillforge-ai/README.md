# SkillForge AI

SkillForge AI is the production-oriented evolution of the interview-preparation platform in this repository. This subtree implements the Supabase + pgvector + FastAPI architecture requested in the August 20, 2026 build contract while preserving the existing Rigor platform work.

## What is checked in now

- Next.js 16 / React 19 / TypeScript frontend starter.
- Working multi-view SaaS demo: dashboard, question bank, Python lab, SQL lab, MCQ, enterprise scenarios, semantic search, progress, learning paths, bookmarks, admin.
- Demo records selected directly from the normalized uploaded question corpus.
- Supabase core schema, RLS policies, full-text search, pgvector HNSW index, hybrid search function.
- FastAPI service with health endpoint, local Python demo execution, seeded read-only SQL execution, and import validation endpoints.
- Dockerfiles and Docker Compose starter.
- AWS deployment architecture notes.

## Source corpus represented by the current normalization

- 24,800 unique question/scenario records.
- 24,800 matched solutions.
- 22 banks.
- 2,000 Python coding questions.
- 3,000 SQL coding questions.
- 1,800 enterprise data-engineering scenarios, 1,090 code-linked.

The full corpus is not committed as a giant generated JSON blob in this first UI commit. The import pipeline should load it into Supabase/Postgres from governed source artifacts rather than making the application bundle itself the database.

## Local startup

```bash
cd skillforge-ai
supabase start
cd infra && docker compose up --build
```

Or run services independently:

```bash
cd frontend && npm install && npm run dev
cd ../backend && python -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt && uvicorn app.main:app --reload
```

## Security boundary

The FastAPI `/runner/python` endpoint in this starter is only a constrained **local demo endpoint**. It is not a production sandbox. Production candidate execution must use separately isolated workloads and must never run in the web container, normal API container, Supabase/RDS database, or client device.
