# Dependency Matrix

This initial matrix covers direct dependencies selected for the first vertical slice. Lockfiles carry the full transitive graph.

| Package | Version | Runtime | License | Purpose | Status |
| --- | ---: | --- | --- | --- | --- |
| next | 16.2.10 | Node 24 | MIT | App Router web application | registry verified; build passed on local Node 26, Node 24 CI pending |
| react / react-dom | 19.2.7 | Node 24 | MIT | UI runtime | registry verified; build and component test passed |
| typescript | 5.9.3 | Node 24 | Apache-2.0 | strict frontend types | selected because the verified OpenAPI generator declares TypeScript 5.x support |
| tailwindcss | 4.3.3 | Node 24 | MIT | styling | registry verified; compile pending |
| @tanstack/react-query | 5.101.3 | Node 24 | MIT | server state | registry verified; compile pending |
| zustand | 5.0.14 | Node 24 | MIT | editor-local state | registry verified; usage deferred |
| zod | 4.4.3 | Node 24 | MIT | client boundary validation | registry verified; compile pending |
| fastapi | 0.139.2 | Python 3.13 | MIT | REST/OpenAPI API | import, OpenAPI export, and API tests passed |
| pydantic | 2.13.4 | Python 3.13 | MIT | canonical schemas | import and schema tests passed |
| sqlalchemy | 2.0.51 | Python 3.13 | MIT | relational persistence | import and PostgreSQL migration passed |
| alembic | 1.18.5 | Python 3.13 | MIT | migrations | clean upgrade/downgrade/upgrade passed |
| psycopg | 3.3.4 | Python 3.13 | LGPL-3.0 | PostgreSQL driver | connection, migration, and seed passed |
| pgvector | 0.5.0 | Python 3.13 | MIT | PostgreSQL vector type integration | resolver verified; migration test pending |
| temporalio | 1.30.0 | Python 3.13 | MIT | durable workflows | resolver verified; import pending |
| opentelemetry-sdk | 1.44.0 | Python 3.13 | Apache-2.0 | telemetry | resolver verified; import pending |
| httpx2 | 2.7.0 | Python 3.13 | BSD-3-Clause | Starlette/FastAPI contract tests | required by installed TestClient; resolver verified |

Security considerations: lock all versions, scan licenses and vulnerabilities in CI, minimize optional extras, and prevent direct provider/cloud calls outside adapters. Official documentation links live in `docs/TECH_STACK_VERIFICATION.md`; repositories are discoverable from their npm/PyPI project metadata and will be captured by the dependency inventory job.
