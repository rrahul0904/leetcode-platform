# Rigor production deployment

## Promotion model

Application images are built once, scanned, identified immutably, deployed to staging, smoke-tested, and only then promoted to production. Production infrastructure apply and production application release require explicit approval.

## Terraform

Staging:

```bash
cd infra/terraform/environments/staging
terraform init -backend-config=backend.hcl
terraform fmt -check -recursive ../../
terraform validate
terraform plan
```

Production:

```bash
cd infra/terraform/environments/production
terraform init -backend-config=backend.hcl
terraform fmt -check -recursive ../../
terraform validate
terraform plan
```

Do not run production `terraform apply` from pull-request validation.

## Application compute gate

`enable_control_plane_compute=false` is the current safe setting. It must remain false until:

- API Run/Submit use durable queued dispatch rather than inline candidate execution;
- the trusted dispatcher is implemented and idempotent;
- staging gVisor nodes are validated;
- execution network-denial/timeout/duplicate-delivery tests pass.

## Database bootstrap

Terraform creates RDS and separate Secrets Manager credentials for `rigor_app` and `rigor_migrator`. Before application compute is enabled, a controlled bootstrap step using the RDS-managed master credential must create/update those PostgreSQL roles and least-privilege grants. Alembic then runs exactly once as `rigor_migrator`.

Do not put migration execution into every API task startup.

## Web build

Production web builds should set `NEXT_PUBLIC_RIGOR_API_URL` to the intended public API origin or an empty value for same-origin routing. Never ship `localhost` in the production browser bundle.

## Mobile

Native binaries release separately from backend deployment. EAS production build/submission is performed only after bundle/application identifiers, associated domains/app links, OIDC redirects, signing, and store credentials are established.

## Rollback

Application rollback uses the previous immutable image/task definition. Database changes follow expand/contract compatibility; destructive contraction is a separate release after old application versions no longer depend on the removed shape.
