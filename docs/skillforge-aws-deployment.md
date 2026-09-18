# SkillForge AWS deployment

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

Expected head: `20260826_0017`.

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
