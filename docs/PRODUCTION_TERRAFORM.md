# Production Terraform usage

## Structure

```text
infra/terraform/
├── modules/
│   ├── networking/
│   ├── iam/
│   ├── kms/
│   ├── ecr/
│   ├── ecs/
│   ├── rds/
│   ├── valkey/
│   ├── storage/
│   ├── queues/
│   ├── execution/
│   ├── observability/
│   ├── waf/
│   └── platform/
└── environments/
    ├── staging/
    └── production/
```

## Validation

```bash
terraform fmt -check -recursive infra/terraform

cd infra/terraform/environments/staging
terraform init -backend=false
terraform validate

cd ../production
terraform init -backend=false
terraform validate
```

A real environment uses its own copied `backend.hcl` (not committed) and production-specific variable values.

## Remote state

The example backend files use S3 encryption and native lock files. The state buckets are bootstrapped separately and must not be shared between staging and production. Terraform state is sensitive because provider-managed secret values can be present even when outputs are marked sensitive; backend access must be tightly controlled.

## Production apply

Pull-request CI performs formatting and validation only. A production `terraform apply` requires a reviewed plan and explicit deployment approval outside the PR validation workflow.

## Current gate

The platform module provisions the data/execution foundation independently from ECS application compute. `enable_control_plane_compute=false` remains the required setting until queued execution is production-safe.
