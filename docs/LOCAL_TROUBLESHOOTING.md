# Local Troubleshooting

## Inspect the stack

```bash
make verify-local
make logs-local
docker compose ps --all
curl --fail --silent http://localhost:8002/readyz
```

`/readyz` reports database, migration, Valkey, content, execution adapter, controller, and runner status without exposing connection strings or credentials.

## Docker build certificate failure

Symptoms include package-manager TLS or certificate errors during image build.

Verify that `infra/certs/local-build-ca.pem` contains an approved CA bundle. On a managed macOS network, export the organization certificate as described in `docs/DOCKER_RELEASE.md`. Never solve this by disabling TLS verification.

## Migration is not ready

Check the database revision:

```bash
docker compose exec -T postgres psql -U rigor -d rigor -Atc \
  "SELECT version_num FROM alembic_version;"
```

Expected local revision:

```text
20260802_0015
```

Inspect migration logs:

```bash
docker compose logs migrate postgres
```

For disposable local data only:

```bash
make reset-local
```

## Controller is unhealthy

```bash
docker compose logs execution-controller
docker compose exec -T execution-controller \
  python -m rigor_api.local_execution_health
```

Inspect the heartbeat:

```bash
docker compose exec -T postgres psql -U rigor -d rigor -x -c \
  "SELECT * FROM local_execution_controller_status;"
```

A healthy row has a fresh heartbeat and both runner flags set to true.

## Python runner is unhealthy

```bash
docker compose logs python-runner
docker compose exec -T python-runner python -c \
  "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8081/healthz').read())"
```

The service has no application database credentials and no public port. Use `docker compose exec` rather than publishing it.

## SQL runner is unhealthy

```bash
docker compose logs sql-runner execution-postgres
docker compose exec -T execution-postgres \
  pg_isready -U rigor_sql_owner -d rigor_execution
```

The execution database is disposable. Restarting `execution-postgres` clears it without affecting application PostgreSQL.

## Execution remains queued

Check queue depth and controller logs:

```bash
docker compose exec -T postgres psql -U rigor -d rigor -Atc \
  "SELECT count(*) FROM local_execution_queue;"
docker compose logs --tail=200 execution-controller
```

Messages become visible again after the visibility timeout if the controller stops before acknowledging them. Durable execution records remain in application PostgreSQL.

## Web cannot reach API

Confirm both readiness endpoints:

```bash
curl --fail http://localhost:8002/livez
curl --fail http://localhost:8002/readyz
curl --fail http://localhost:3001
```

The Web service waits for a healthy API. Resolve API readiness rather than removing the dependency.

## Backup or restore fails

Check:

- the backup directory contains `manifest.env` and `rigor.dump`;
- the dump is non-empty;
- `sha256sum` or `shasum` exists;
- the manifest checksum has not changed;
- sufficient disk space is available;
- no external client is continuously reconnecting to PostgreSQL.

Restore intentionally fails closed on checksum, schema, or representative-count mismatch.

## Port conflict

The default host ports are 3001, 8002, 5434, and 6381. Stop the conflicting process or adjust the published port in a local Compose override. Do not publish the internal runner or execution-database ports.
