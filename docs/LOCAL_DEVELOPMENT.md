# Local Development Plan

Standard development will use Node 24, Python 3.13, pnpm, uv, and Docker Compose services for PostgreSQL/pgvector, Valkey, MinIO, Temporal, mock OIDC, OpenTelemetry Collector, Prometheus, and Grafana. Kubernetes is not required for ordinary web/API work.

A separate kind or k3d profile will exercise the controller contract and gVisor when the host supports it. Local Docker execution is developer testing only and must never be represented as the production security boundary.

The reproducible Docker workflow is:

```bash
make bootstrap
```

It validates Docker Compose, builds the locked images, waits on the PostgreSQL
and Valkey health checks through Compose dependencies, migrates, seeds,
synchronizes hosted content, runs the local publication workflow, starts the API
and web application, and verifies health and database counts.

To deliberately destroy local development data and recreate it:

```bash
make reset-local
```

`reset-local` removes only this Compose project's containers, orphans, and named
volumes before running the same bootstrap workflow.

Verified foundation commands are:

```bash
uv --system-certs sync --all-packages
pnpm install --frozen-lockfile
docker compose up -d postgres
uv run alembic upgrade head
uv run uvicorn rigor_api.main:app --app-dir apps/api/src --reload --port 8002
pnpm --filter @rigor/web dev
scripts/validate-content
scripts/check-duplicates
scripts/execute-solutions
```

The active shell currently runs Node 26, so the successful frontend build is useful evidence but Node 24 production compatibility still requires a Node 24 CI run.
