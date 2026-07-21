# Technology Stack Baseline

Verified on 2026-07-20. Exact transitive versions are authoritative in `pnpm-lock.yaml` and `uv.lock` once generated.

| Layer | Selected baseline |
| --- | --- |
| Node | 24.18.0 LTS |
| Web | Next.js 16.2.10, React 19.2.7, TypeScript 5.9.3 |
| Styling | Tailwind CSS 4.3.3 |
| Python | CPython 3.13.5 locally; `>=3.13,<3.14` application contract |
| API | FastAPI 0.139.2, Pydantic 2.13.4 |
| Persistence | SQLAlchemy 2.0.51, Alembic 1.18.5, Psycopg 3.3.4 |
| Durable workflows | Temporal Python SDK 1.30.0 |
| Database | PostgreSQL 18.x with pgvector |
| Cache | Valkey-compatible Redis protocol |
| Telemetry | OpenTelemetry SDK 1.44.0 |

Production container tags and GitHub Actions must be pinned by digest or immutable SHA before deployment.
