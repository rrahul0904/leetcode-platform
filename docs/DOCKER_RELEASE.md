# Local Docker Release

## Scope

The local Docker release packages the implemented Rigor application:

- Next.js Web;
- FastAPI API and local OIDC;
- PostgreSQL 18 with pgvector and trigram search;
- Valkey;
- idempotent migrations, taxonomy seeds, source synchronization, and local publication;
- durable local execution controller;
- dedicated Python runner;
- dedicated SQL runner;
- separate disposable execution PostgreSQL.

The release is intended for a trusted local development machine. It does not claim production gVisor isolation, cloud readiness, mobile completion, payments, or public-launch readiness.

## Build trust

On a managed network that intercepts TLS, place the organization-approved root certificate in:

```text
infra/certs/local-build-ca.pem
```

The certificate is mounted as a BuildKit secret only during dependency resolution and is not copied into final images. Do not disable TLS verification.

## Start

```bash
make bootstrap
```

Published surfaces:

- Web: `http://localhost:3001`
- API: `http://localhost:8002`
- application PostgreSQL: `localhost:5434`
- Valkey: `localhost:6381`

The controller, runners, and execution PostgreSQL are internal-only.

## Service order

1. application PostgreSQL and Valkey become healthy;
2. Alembic migrates to the single head;
3. deterministic seeds are applied;
4. approved external references are synchronized;
5. hosted content is synchronized;
6. the controlled local cohort is published;
7. execution PostgreSQL, Python runner, and SQL runner become healthy;
8. the local controller starts and reports a heartbeat;
9. the API starts only after controller and runners are ready;
10. the Web starts only after API readiness passes.

## Runtime hardening

Application and execution services use combinations of:

- non-root users where practical;
- read-only root filesystems;
- bounded `tmpfs` storage;
- dropped Linux capabilities;
- `no-new-privileges`;
- CPU, memory, and process limits;
- explicit application and internal execution networks;
- no Docker socket;
- no host source-code mounts;
- no cloud credentials in runner services;
- no application database credentials in runner services.

Candidate SQL uses only the disposable `execution-postgres` service.

## Inspect and stop

```bash
make verify-local
make logs-local
make stop-local
```

`stop-local` preserves the application PostgreSQL volume. `reset-local` removes it and must be deliberate:

```bash
make backup-local
make reset-local
```

## Release validation

```bash
make release-local
```

This gate validates locked dependencies, Web and Python quality checks, a clean Compose build, migrations, populated startup, dependency health, and backup/restore.

GitHub Actions separately builds all three execution images, rejects HIGH/CRITICAL fixed vulnerabilities through Trivy, and publishes CycloneDX SBOM artifacts.

## Image tags

Local images use:

```text
rigor-web:0.1.0-local
rigor-api:0.1.0-local
rigor-execution-controller:0.1.0-local
rigor-python-runner:0.1.0-local
rigor-sql-runner:0.1.0-local
```

Registry publication and cloud deployment are outside the local milestone. Production images require immutable digests, signing, attestations, cloud secrets, and the separate Kubernetes/gVisor execution architecture.
