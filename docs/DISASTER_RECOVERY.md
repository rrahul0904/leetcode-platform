# Rigor disaster recovery baseline

## Canonical vs reconstructable components

Canonical production state:

- RDS PostgreSQL candidate/content/submission/evidence/readiness state;
- selected durable S3 artifacts;
- Terraform state.

Non-canonical/reconstructable:

- Valkey cache/rate-limit/short-lived locks;
- ECS tasks;
- EKS sandbox Jobs;
- transient execution artifacts after their retention period.

## Initial objectives

These are engineering targets pending business approval and restore exercises, not validated commitments.

| Component | Initial RPO target | Initial RTO target |
| --- | ---: | ---: |
| RDS PostgreSQL | <= 5 minutes via PITR capability | <= 2 hours |
| durable S3 artifacts | <= 15 minutes / versioning semantics | <= 2 hours |
| Terraform state | each committed state mutation | <= 1 hour |
| Valkey | no canonical RPO requirement | <= 1 hour |
| ECS services | image/config reproducible | <= 1 hour after data dependencies |
| execution plane | no sandbox state recovery requirement | <= 2 hours; queued requests reconciled |

## Required restore exercise

1. Restore the latest acceptable RDS recovery point into an isolated recovery environment.
2. Use separate security groups and credentials; never point the recovery test at production writers.
3. Verify Alembic head and required PostgreSQL extensions.
4. Run candidate-safe API smoke tests against the restored database.
5. Verify representative profile, practice history, submission, evidence, and readiness records.
6. Restore/version-read representative S3 artifacts.
7. Recreate disposable Valkey/ECS/execution infrastructure from Terraform/release artifacts.
8. Record measured recovery time and data gap.
9. Update RPO/RTO only after measured evidence exists.

A configured backup is not considered validated until this restore test has succeeded.
