# Production release gates

Production enablement is sequential.

## Gate 1 — repository quality

- frozen pnpm install;
- JS lint/typecheck/tests/build;
- backend pytest/Ruff/Pyright;
- one Alembic head;
- Terraform fmt/init/validate;
- API/web production Docker builds.

## Gate 2 — async execution correctness

- outbox + SQS publish;
- atomic worker claims;
- target execution state machine;
- duplicate delivery safety;
- cancellation/reconciliation;
- client polling/stream contract.

## Gate 3 — staging infrastructure

- RDS/Valkey/S3/SQS/ECR/EKS applied;
- database roles bootstrapped;
- validated runsc AMI/node group;
- sandbox network/metadata/resource tests;
- Python and disposable SQL executions succeed;
- queue-based scaling/alarms tested.

## Gate 4 — staging application

Only after Gates 1–3 set `enable_control_plane_compute=true` in staging with immutable image digests. Verify web/native auth, practice, run, submit, persistence, evidence/readiness, failure modes, and rollback.

## Gate 5 — recovery/security

- RDS restore exercise;
- S3 recovery/version check;
- incident runbooks;
- IAM/KMS/S3/security-group review;
- WAF/quota testing;
- monitoring subscriptions and paging path.

## Gate 6 — production

Reviewed Terraform plan + explicit approval, controlled database migration, immutable release promotion, health/smoke/isolation tests, and monitored rollout.

No gate is satisfied merely because later-gate Terraform exists in source.
