# Rigor Interview Systems Lab

Rigor is an independent, evidence-driven technical interview preparation platform for experienced engineers. It targets senior through principal roles across software, data, machine learning, AI infrastructure, architecture, and technical leadership.

> Rigor is independent and is not affiliated with, endorsed by, or sponsored by any employer. Company-style tracks are original curricula based on public engineering themes. Compensation, interview, and employment outcomes are not guaranteed.

## Local application

The repository provides a complete Docker Compose topology for local use:

- Next.js Web application;
- FastAPI API and local OIDC provider;
- PostgreSQL 18 with pgvector for application data;
- Valkey;
- idempotent migrations, seeds, source synchronization, and local publication;
- durable local execution controller;
- dedicated Python 3.13 runner;
- dedicated SQL runner;
- a separate disposable PostgreSQL instance for candidate SQL.

Start the populated local application:

```bash
make bootstrap
```

Published surfaces:

```text
Web: http://localhost:3001
API: http://localhost:8002
```

The startup workflow builds images, migrates and seeds PostgreSQL, synchronizes approved sources and hosted packages, publishes the controlled local cohort, starts the execution controller and both runners, verifies dependency health, and checks content counts.

Useful commands:

```bash
make verify-local
make logs-local
make stop-local
make reset-local
make backup-local
make restore-local BACKUP=backups/rigor-local-<timestamp>
make release-local
```

Read:

- [Local development](docs/LOCAL_DEVELOPMENT.md)
- [Local environment](docs/LOCAL_ENVIRONMENT.md)
- [Local execution](docs/LOCAL_EXECUTION.md)
- [Backup and restore](docs/LOCAL_BACKUP_RESTORE.md)
- [Troubleshooting](docs/LOCAL_TROUBLESHOOTING.md)
- [Docker release](docs/DOCKER_RELEASE.md)
- [Implementation ledger](IMPLEMENTATION_PROGRESS.md)

## Execution boundary

The Web and API containers never execute candidate code. Python and SQL requests use the durable execution aggregate and transactional outbox, then flow through the local controller to dedicated internal runner services. Candidate SQL uses `execution-postgres`, never application PostgreSQL.

The local Docker path is intended for a trusted development machine and functional validation. It is not equivalent to production hostile-code isolation. Production execution remains designed for cloud queues, Kubernetes Jobs, containerd, gVisor, dedicated hostile-execution nodes, and adversarial staging evidence.

## Content platform

The 1,350-question manifest is a launch-foundation benchmark, not a ceiling or a published bank. A hosted question counts as published only after its structured package passes automated validation, rights checks, duplicate analysis, technical review, editorial review, and publication gates. External references are counted separately.

The universal ingestion CLI is available as `./scripts/content`:

```bash
./scripts/content validate <path>
./scripts/content import <path> --dry-run
./scripts/content import <path>
./scripts/content check-duplicates <path>
./scripts/content execute-solutions <path>
./scripts/content validate-rights <path>
./scripts/content sync-postgres <path>
./scripts/content report <import-id>
./scripts/content rollback <import-id>
```

AI-assisted packages enter controlled factory batches of at most ten questions. Every result receives a durable generation trace and no batch publishes automatically.

Run reviewed metadata-only connectors with:

```bash
SSL_CERT_FILE="$PWD/infra/certs/local-build-ca.pem" ./scripts/collect-external-references \
  --ca-file "$PWD/infra/certs/local-build-ca.pem"
```

Prohibited, credentialed, and unlicensed sources remain blocked or paused rather than scraped. See [Source catalog](docs/SOURCE_CATALOG.md).

## Architecture

- `apps/web`: Next.js App Router and TypeScript Web application
- `apps/api`: FastAPI modular-monolith API
- `services`: execution controller and isolated runtime boundaries
- `packages`: shared schemas, generated API types, editors, and telemetry
- `content`: version-controlled question plans and packages
- `database`: Alembic migrations, roles, RLS, and controlled seeds
- `infra`: Docker, Terraform, Kubernetes sandbox definitions, and policies
