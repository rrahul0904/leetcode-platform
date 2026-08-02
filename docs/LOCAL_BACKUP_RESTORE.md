# Local Backup and Restore

## Backup

Create a backup while the stack is running:

```bash
make backup-local
```

The command prints a directory such as:

```text
backups/rigor-local-20260802T231500Z
```

Each backup contains:

```text
manifest.env
rigor.dump
```

The manifest records:

- format version;
- UTC creation time;
- Alembic schema revision;
- Git application revision;
- dump file name;
- SHA-256 checksum;
- question count;
- published-version count;
- execution-request count.

The PostgreSQL dump includes application data and database privileges. It does not include Valkey data, runner filesystems, the disposable execution PostgreSQL instance, access tokens, or cloud credentials.

Backups are ignored by Git. Treat them as sensitive local data because they can contain candidate profiles, notes, drafts, source code, and execution history.

## Restore

Restore by passing either the backup directory or its manifest:

```bash
make restore-local BACKUP=backups/rigor-local-20260802T231500Z
```

The restore workflow:

1. validates the manifest version;
2. rejects unsafe dump paths;
3. verifies the SHA-256 checksum;
4. stops Web, API, controller, and runner services;
5. terminates remaining application-database sessions;
6. restores PostgreSQL with `--clean --if-exists`;
7. verifies the Alembic revision;
8. verifies representative record counts;
9. reruns the idempotent populated startup workflow;
10. verifies the complete application health contract.

A failed checksum, schema mismatch, or record-count mismatch stops the restore.

## Clean recovery exercise

The local release gate performs a backup/restore cycle automatically:

```bash
make release-local
```

For a deliberate destructive recovery exercise:

```bash
make bootstrap
make backup-local
# Record the printed backup directory.
docker compose down --volumes --remove-orphans
make restore-local BACKUP=backups/rigor-local-<timestamp>
make verify-local
```

Do not delete the backup until the restored application and representative user workflows have been inspected.

## Compatibility

The restore script verifies the schema stored in the backup. A backup from an older supported revision can be restored and then migrated by the normal startup workflow. A backup from an unknown future revision must not be forced into an older checkout.
