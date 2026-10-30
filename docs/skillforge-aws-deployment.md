# SkillForge AWS deployment

For the active cutover sequence and go/no-go gates, see `docs/LAUNCH_WEEK_2026-09-27.md`.

## 1. Provision infrastructure

Use `infra/terraform/environments/dev` for a cloud development environment and `infra/terraform/environments/prod` for production. Local development continues to use Docker Compose.

```bash
cd infra/terraform/environments/prod
cp terraform.tfvars.example terraform.tfvars
terraform init
terraform plan
terraform apply
```

Production creates the VPC/private subnets, ECS Fargate application cluster, ALB, Aurora PostgreSQL, encrypted Valkey, SQS/DLQ, private S3 buckets, ECR repositories, Secrets Manager placeholders, ACM certificate, Route 53 API record, regional WAF, CloudWatch logs, and CloudFront API distribution.

## 2. Populate secrets

Terraform intentionally creates secret containers without committing or generating application credentials in source control. Populate the Secrets Manager values out of band for:

- `RIGOR_DATABASE_URL`
- `RIGOR_OPERATIONAL_DATABASE_URL`
- `RIGOR_VALKEY_URL`
- `CLERK_WEBHOOK_SECRET`
- `SENTRY_DSN`

Use a least-privilege application DB user; do not use the Aurora master user for the API.

## 3. Configure Clerk

Production disables local OIDC. Configure the Clerk issuer, JWKS URL, JWT audience, social providers, MFA policy, and the user/session webhook target:

`https://<api-domain>/api/v1/webhooks/clerk`

The API validates Svix signatures and replay windows before touching identity state.

## 4. Database migration

Run migrations with the migrator database role before deploying a new API revision:

```bash
uv run alembic upgrade head
```

Candidate head: `20261028_0025`. Migration is not authorized until a staged restore/rehearsal and operator go/no-go.

## 5. GitHub deployment variables

Configure repository/environment variables:

- `AWS_REGION`
- `AWS_DEPLOY_ROLE_ARN`
- `ECS_CLUSTER`
- `ECS_API_SERVICE`
- `ECS_WORKER_SERVICE`
- `ECR_API_REPOSITORY`
- `ECR_WORKER_REPOSITORY`

The deployment workflow uses GitHub OIDC; no long-lived AWS access keys are required.

## 6. Release gate

A production release is not complete until migrations, health/readiness, the trusted question-bank verifier, and representative Run/Submit execution checks pass against the deployed environment.


## Self-hosted web release requirement (2026-10-27)

Production Terraform now also defines a private ECS/Fargate web service with its own public HTTPS ALB, WAF, DNS, ACM certificate, logs and autoscaling, plus an ECR repository and a Secrets Manager key for the production Clerk secret.

The production Terraform plan requires web_domain, web_image and clerk_publishable_key. An operator must provide a customer-owned web domain, real Clerk keys, immutable scanned web image in ECR, trusted OIDC AWS access and managed remote Terraform state. Populate the CLERK_SECRET_KEY Secrets Manager value before launching ECS web tasks. Never reapply Terraform locally against production resources without state import/reconciliation.

The guarded workflow deploy-ecs-web.yml deploys the selected SHA only after validating HTTPS domain, Clerk issuer, live public key, CORS allowlist and upstream API readiness at Alembic 20261028_0025. Deployment uses a fail-closed image vulnerability scan, ECS service stability, HTTPS smoke and rollback.

A passing Terraform validation or standalone image boot test does not certify an AWS deployment. Signed content rights, verified full employer coding assessment, candidate UAT, backup/restore receipts and protected production authorization remain mandatory.
