# SkillForge AI architecture

## Runtime split

- **Next.js 16 / React 19**: SaaS UI, authenticated app shell, search, practice, admin, streaming AI UX.
- **Supabase**: Postgres, Auth, Storage, RLS, pgvector, lightweight Edge Functions.
- **FastAPI**: code-execution orchestration, bulk import/export, background AI/embedding jobs, enterprise APIs.
- **Redis + worker**: durable job queue and rate/usage coordination.
- **Production runner**: isolated per-execution workloads. Candidate code never runs in the web process, API process, Supabase database, or mobile/browser environment.

## Search

Hybrid ranking combines Postgres full-text search and pgvector cosine similarity. `question_embeddings` uses HNSW from the first migration. Vector-store access is kept behind a repository boundary so Pinecone, Qdrant, OpenSearch Serverless, Bedrock Knowledge Bases, and other stores can be added later.

## AI

AI is provider-agnostic and optional for core practice. The intended UI path uses Vercel AI SDK streaming; retrieval comes from Supabase; batch embedding/content workflows run in FastAPI workers. Full solutions are not revealed by default in tutor mode.

## Source-backed content

The demo sample records in `frontend/lib/demo-data.ts` are selected directly from the uploaded normalized 24,800-record corpus. Full-corpus import remains a governed data operation: validate → review → import → embed → publish. Alternate PDF/DOCX renderings are provenance, not duplicate questions.

## Production path

Fastest path: Vercel/Amplify frontend + Supabase Cloud + ECS Fargate API/workers + ElastiCache/Upstash Redis + S3 + CloudWatch/Sentry.

Enterprise AWS-native path: CloudFront/Amplify + ECS Fargate + Aurora PostgreSQL pgvector/OpenSearch Serverless + Cognito/Supabase Auth alternative + S3 + SQS + ElastiCache + Bedrock + Secrets Manager + Terraform.
