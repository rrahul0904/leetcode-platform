# Technology Stack Verification

## Evidence captured

- Local runtimes: Node `v26.4.0`, pnpm `11.10.0`, Python `3.13.5`, uv `0.11.26`. Development is constrained to Node 24 through `engines` and `.nvmrc`; the currently active Node 26 is a compatibility warning, not the approved production runtime.
- Node 24.18.0 is the newest 24.x LTS patch listed by the official Node release index on the verification date.
- Next.js 16.2.10 and frontend package versions were resolved from the npm registry with `pnpm view`.
- Python versions were resolved in a clean temporary Python 3.13 environment with uv using system trust certificates. Minimal imports and compilation are part of repository verification tests.
- TypeScript 7.0.2 was rejected after the pinned OpenAPI generator failed and its package metadata declared `^5.x`; TypeScript 5.9.3 is the newest compatible 5.x patch. API types remain generated rather than duplicated.
- ESLint 10.7.0 was rejected after the verified Next.js configuration's React plugin failed under its changed rule context. ESLint 9.39.5 satisfies the Next.js peer range and is the tested baseline.
- PostgreSQL 18/AWS service availability, container digests, gVisor/EKS compatibility, and production provider capabilities remain `UNVERIFIED` until infrastructure work begins. Production functionality must not assume them silently.

## Official sources

- Node releases: https://nodejs.org/en/about/previous-releases
- Next.js documentation: https://nextjs.org/docs
- FastAPI release notes: https://fastapi.tiangolo.com/release-notes/
- Pydantic documentation: https://docs.pydantic.dev/latest/
- SQLAlchemy documentation: https://docs.sqlalchemy.org/en/20/
- Temporal Python SDK: https://docs.temporal.io/develop/python
- PostgreSQL documentation: https://www.postgresql.org/docs/

## Verification rule

No dependency moves from `UNVERIFIED` to `VERIFIED` until it is locked, imported or compiled in the approved runtime, and its used API is exercised by a focused test.
