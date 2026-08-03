# Local Development

## Complete Docker application

Run the populated local application with:

```bash
make bootstrap
```

The workflow validates Compose, builds locked application and execution images, starts PostgreSQL and Valkey, migrates and seeds the application database, synchronizes approved content, publishes the controlled local cohort, starts the local execution controller, starts dedicated Python and SQL runners, and waits for Web/API/execution readiness.

Kubernetes is not required for ordinary Web, API, content, or local execution development.

## Lifecycle

```bash
make verify-local
make logs-local
make stop-local
make reset-local
```

- `verify-local` validates Compose, API readiness, Web availability, controller heartbeat, and runner health.
- `stop-local` removes containers and networks while preserving application data.
- `reset-local` deletes the application PostgreSQL volume and reconstructs the complete populated stack.

## Data protection

```bash
make backup-local
make restore-local BACKUP=backups/rigor-local-<timestamp>
```

See `docs/LOCAL_BACKUP_RESTORE.md` before a destructive reset.

## Full local release gate

```bash
make release-local
```

This runs locked dependency installation, Web lint/type/tests/build, Python Ruff/Pyright/tests, a clean Docker build and bootstrap, dependency verification, and backup/restore verification.

Container vulnerability scans and SBOM generation remain enforced in GitHub Actions for the execution images.

## Host-side development

Use Node 24.18.x, pnpm 11.10.x, Python 3.13, and `uv`.

```bash
uv sync --frozen --all-packages
pnpm install --frozen-lockfile
docker compose up -d postgres valkey
RIGOR_DATABASE_URL=postgresql+psycopg://rigor_migrator:rigor_migrator_local_only@localhost:5434/rigor \
  uv run alembic upgrade head
uv run uvicorn rigor_api.main:app --app-dir apps/api/src --reload --port 8002
pnpm --filter @rigor/web dev
```

Host-side API development defaults to `LOCAL_FUNCTIONAL`. The complete Compose application explicitly uses `LOCAL_DOCKER`. Both adapters are rejected in staging and production.

## Content validation

```bash
make test-content
./scripts/content validate <path>
./scripts/content check-duplicates <path>
./scripts/content execute-solutions <path>
```

Executable reference packages run in isolated Python subprocesses so package-local modules cannot collide during collection.

## Local execution boundary

Local candidate code does not run in the Web or API containers. The controller sends requests to dedicated internal runner services, and candidate SQL uses a separate disposable PostgreSQL service.

This is still a development boundary. Do not describe it as production gVisor isolation or expose it as a public multi-tenant execution service. See `docs/LOCAL_EXECUTION.md`.
