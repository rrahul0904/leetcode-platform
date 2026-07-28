# Rigor production architecture

```text
Internet
   |
   v
CloudFront / edge (planned)
   |
   v
WAF + ALB
   |-----------------------|
   v                       v
Next.js ECS Fargate    FastAPI ECS Fargate
                           |
             |-------------|-------------|
             v             v             v
          RDS PG         Valkey          S3
                           |
                           v
                   execution request
                           |
                           v
                          SQS
                           |
                           v
                  trusted dispatcher
                           |
                           v
                  private execution EKS
                     containerd + gVisor
                      |              |
                      v              v
                   Python      disposable SQL PG
```

## Control plane

Normal SaaS workloads use ECS Fargate and scale independently. The database and cache are private data-subnet resources. S3 buckets are private and encrypted. Authentication remains OIDC/FastAPI authorization.

## Execution plane

Untrusted code runs only in the separate EKS execution plane. Execution subnets do not have a default internet route. Kubernetes pods use the `gvisor` RuntimeClass, restricted pod security, no ServiceAccount token, deny-all networking, non-root users, dropped capabilities, read-only root filesystems, seccomp, and bounded resources.

## Environment isolation

Staging and production use separate Terraform roots with different VPC CIDRs and state keys. They create separate RDS, Valkey, S3, SQS, ECR, KMS, and EKS resources. OIDC issuer/audience/origin configuration is supplied independently per environment.

## Deployment gate

The reusable platform module sets application compute behind `enable_control_plane_compute`. Both environment roots default it to false. This is intentional until candidate Run/Submit no longer performs inline local execution in FastAPI.

## Images

Production deployment consumes immutable ECR image references. The web image's API origin is a build artifact: production should compile to same-origin API requests behind the edge/ALB rather than baking a developer `localhost` address into the browser bundle.

## Data

RDS PostgreSQL is canonical. Valkey is non-canonical cache/quota/coordination state only. Candidate SQL uses disposable PostgreSQL inside the execution plane and never application RDS.

## Credentials

RDS master credentials are RDS-managed and reserved for bootstrap/recovery. Runtime application and migrator credentials are separate Secrets Manager records. ECS injects individual secret fields; FastAPI composes TLS DSNs at runtime.

## Current release status

The architecture is implemented as source/Terraform on the feature branch but has not been applied to AWS. `gvisor_node_group_created=false` is expected until a validated custom runsc AMI and bootstrap configuration are provided. Production compute must remain disabled until the queued dispatcher milestone is complete.
