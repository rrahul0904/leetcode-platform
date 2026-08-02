# Local Environment

## Prerequisites

The complete local application requires:

- Docker Desktop or Docker Engine with Docker Compose v2;
- Git;
- `curl`;
- Node 24.18.x and pnpm 11.10.x for host-side Web validation;
- Python 3.13 and `uv` for host-side API validation.

The normal application startup requires only Docker, Compose, and `curl` because application dependencies are built into images.

## Commands

```bash
make bootstrap
make verify-local
make logs-local
make stop-local
make reset-local
make backup-local
make restore-local BACKUP=backups/rigor-local-<timestamp>
make release-local
```

`reset-local` removes the application PostgreSQL volume. `stop-local` preserves it.

## Published local ports

| Surface | URL or port | Purpose |
| --- | --- | --- |
| Web | `http://localhost:3001` | Candidate and administration application |
| API | `http://localhost:8002` | FastAPI, local OIDC, and execution APIs |
| PostgreSQL | `localhost:5434` | Application database for local diagnostics |
| Valkey | `localhost:6381` | Local cache and coordination |

The controller, Python runner, SQL runner, and execution PostgreSQL are internal-only and do not publish host ports.

## Environment variables

`.env.example` documents host-side defaults. Docker Compose supplies internal service URLs and local-only credentials directly to the services that need them.

Important settings:

| Variable | Local meaning |
| --- | --- |
| `RIGOR_ENVIRONMENT` | `local` in the complete Compose application |
| `RIGOR_EXECUTION_ADAPTER` | `LOCAL_DOCKER` in Compose; `LOCAL_FUNCTIONAL` for narrow host-side development |
| `RIGOR_DATABASE_URL` | Application-role PostgreSQL connection |
| `RIGOR_OPERATIONAL_DATABASE_URL` | Read-only operational connection |
| `RIGOR_EXECUTOR_DATABASE_URL` | Execution-worker connection available only to the controller |
| `RIGOR_VALKEY_URL` | Valkey connection |
| `RIGOR_LOCAL_PYTHON_RUNNER_URL` | Internal Python runner URL |
| `RIGOR_LOCAL_SQL_RUNNER_URL` | Internal SQL runner URL |
| `RIGOR_BACKUP_ROOT` | Host directory for generated backups |

`LOCAL_FUNCTIONAL` and `LOCAL_DOCKER` are rejected when the environment is `staging` or `production`.

## Build certificate

`infra/certs/local-build-ca.pem` is supplied as a Docker BuildKit secret during dependency installation. It must contain an organization-approved or public CA bundle. Do not disable TLS verification and do not copy the certificate into a runtime image.

## Local-only credentials

Passwords in `compose.yaml` and `database/init/001_roles.sql` are intentionally local-only. They must never be reused for a shared environment. No real secret belongs in `.env`, source control, a runner payload, or a backup manifest.
