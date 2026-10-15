# Terraform

SkillForge/Rigor uses Terraform for the hosted AWS control plane and isolated candidate-execution plane. These definitions are deployment code; they do not imply that an AWS account has already been provisioned.

## Canonical environments

- `environments/dev` — hosted development control plane.
- `environments/staging` — execution-isolation proving ground and adversarial certification environment.
- `environments/prod` — production ECS/API/data plane plus the guarded hostile-code execution plane.

The former empty `development` and `production` placeholders were removed during the reconstruction so there is one authoritative environment path per stage.

## Production boundary

The application plane uses ECS, managed PostgreSQL, Valkey, S3, SQS, WAF, Route 53 and CloudFront. Candidate code never executes in the API or Web containers. Production candidate execution is a separate, explicitly enabled EKS plane with:

- an isolated execution VPC and no-Internet hostile-execution subnets;
- a hardened custom execution-node AMI with `runsc`/containerd integration;
- a KMS-protected SQS request queue and dead-letter queue;
- a trusted controller identity with least-privilege queue access;
- a separate execution database boundary;
- private EKS API access by default.

`enable_execution_production_infrastructure` defaults to `false`. Enabling it requires a hardened execution AMI. Candidate execution must not be exposed to users until the execution plane and its adversarial certification have passed.

## State and promotion requirements

Production state must use encrypted remote state and locking, environment-specific deployment roles, policy checks, reviewed plans, immutable image references, and change evidence. Secrets belong in the configured secret-management path, never in committed tfvars.

Validation is performed by `.github/workflows/terraform-saas.yml` for the canonical hosted environments.
