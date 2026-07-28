# Rigor incident response baseline

## Severity examples

Critical security incidents include suspected sandbox escape, candidate access to another candidate's data, AWS credential exposure from a sandbox, application RDS access from the execution plane, hidden-test disclosure at scale, or unauthorized production deployment.

Reliability incidents include sustained execution queue backlog, repeated sandbox infrastructure errors, RDS unavailability, corrupted migrations, authentication outage, or failed deployment with candidate impact.

## First actions

1. Preserve evidence and correlation identifiers; do not copy candidate source/hidden tests into broad chat/ticket systems.
2. Stop unsafe execution by disabling dispatch/worker capacity rather than shutting down canonical candidate state where possible.
3. Block compromised credentials/roles and rotate secrets/KMS grants as appropriate.
4. Keep queued execution IDs durable for later reconciliation.
5. Roll back immutable application images/config if an application release caused the incident.
6. For data incidents, isolate recovery operations from production writers.

## Execution containment

The execution plane is disposable. During a sandbox/security incident it is acceptable to scale execution capacity to zero, stop dispatch, delete active Jobs, and leave execution rows queued/reconcilable while preserving the control plane.

## Required runbooks before production

- RDS restore/PITR;
- leaked credential rotation;
- EKS execution shutdown/rebuild;
- SQS/DLQ redrive;
- orphaned execution reconciliation;
- bad migration recovery;
- OIDC outage/fallback communication;
- mobile/web release rollback.

## Post-incident

Record root cause, blast radius, candidate impact, timeline, detection gap, recovery evidence, and the automated test/control that will prevent recurrence. Security acceptance tests must be expanded when an isolation assumption fails.
