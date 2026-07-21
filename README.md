# Rigor Interview Systems Lab

Rigor is an independent, evidence-driven technical interview preparation platform for experienced engineers. It targets senior through principal roles across software, data, machine learning, AI infrastructure, architecture, and technical leadership.

> Rigor is independent and is not affiliated with, endorsed by, or sponsored by any employer. Company-style tracks are original curricula based on public engineering themes. Compensation, interview, and employment outcomes are not guaranteed.

## Current status

The repository is building a continuously expanding content-intelligence platform. The 1,350-question manifest is the launch-foundation benchmark, not a ceiling or final bank. A hosted question counts as published only after its structured package passes automated validation, rights checks, duplicate analysis, technical review, editorial review, and publication gates; external references are counted separately.

The universal ingestion CLI is available as `./scripts/content`. Its verified command surface is:

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

AI-assisted packages enter through controlled factory batches of at most ten questions. A batch is single-track unless mixed mode is explicitly enabled, every result receives a durable generation trace, and no batch can publish automatically.

The source-backed competency catalog is populated before original content generation. Run the reviewed metadata-only connectors with:

```bash
SSL_CERT_FILE="$PWD/infra/certs/local-build-ca.pem" ./scripts/collect-external-references \
  --ca-file "$PWD/infra/certs/local-build-ca.pem"
```

The current legal backfill contains 2,534 external references and 5,990 competency mappings from official APIs or explicitly licensed repositories. Prohibited, credentialed, and unlicensed sources are blocked or paused rather than scraped. See [docs/SOURCE_CATALOG.md](docs/SOURCE_CATALOG.md).

The implemented foundation is published locally as hardened Docker images:

- Web: `http://localhost:3001`
- API: `http://localhost:8002`

Start the complete populated application with one idempotent command:

```bash
./scripts/start-populated-local
```

The command builds the images, migrates and seeds PostgreSQL, runs approved
collectors, validates and imports hosted packages, exercises the distinct local
review roles, publishes PY-0002 through PY-0004, verifies non-zero counts, and
prints the browser URL. It fails if fewer than 2,000 external references or
three published hosted questions are present.

See [docs/DOCKER_RELEASE.md](docs/DOCKER_RELEASE.md) for lifecycle and build-trust instructions.

See [docs/PROGRESS.md](docs/PROGRESS.md) for an honest implementation ledger.

The local web release includes functional routes for the foundation dashboard, planned question catalog and safe detail views, learning-path selection, deterministic mock-session planning, an autosaving design workspace, readiness reporting, content review evidence, quality gates, and local reviewer-assignment validation. Features that require trustworthy identity, publication, AI processing, or isolated execution remain visibly gated rather than simulated as production-ready.

## Architecture

- `apps/web`: Next.js App Router and TypeScript web application
- `apps/api`: FastAPI modular-monolith API
- `services`: security and scaling boundaries for execution and durable workers
- `packages`: shared schemas, generated client types, UI, editors, and telemetry
- `content`: version-controlled question plans and independently versioned packages
- `database`: migrations and controlled seeds
- `infra`: Terraform, Kubernetes sandbox definitions, and policies

The application plane never executes candidate code. Production execution is designed for isolated Kubernetes Jobs using containerd and gVisor.

## Baseline commands

Commands are added only after they have been exercised against the locked versions. See `docs/LOCAL_DEVELOPMENT.md` for verified and pending commands.

For the populated local Docker release, run `./scripts/start-populated-local`.
