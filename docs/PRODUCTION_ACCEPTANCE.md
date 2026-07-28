# Rigor production acceptance matrix

Use only `PASS`, `FAIL`, `BLOCKED`, or `NOT_IMPLEMENTED`. Terraform source alone is not evidence that AWS behavior passed.

| Requirement | Current implementation evidence | Status |
| --- | --- | --- |
| Shared web/iOS/Android backend | Expo client uses generated FastAPI contracts and canonical candidate APIs | PASS (source) |
| Native OIDC + PKCE | Expo AuthSession + SecureStore | PASS (source) |
| Persistent native code drafts | Expo SQLite local-first draft store | PASS (source) |
| Web/mobile cross-device state | Both clients target FastAPI/PostgreSQL state | BLOCKED on device/E2E verification |
| Private RDS | Terraform data subnets + SG allow list | BLOCKED on AWS apply verification |
| RDS encryption/TLS/backups | Terraform KMS, force SSL, retention/PITR configuration | BLOCKED on AWS apply + restore test |
| Private Valkey | Terraform data subnets, TLS/auth/KMS | BLOCKED on AWS apply verification |
| Private S3 | public block + KMS + lifecycle/versioning | BLOCKED on AWS apply verification |
| SQS + DLQ | encrypted queue/redrive policy | BLOCKED on AWS apply verification |
| Application ECS Fargate | Terraform module exists but environment compute defaults off | BLOCKED by async execution milestone |
| Separate execution EKS | private cluster Terraform exists | BLOCKED on AWS apply verification |
| Validated gVisor nodes | node group requires custom AMI/bootstrap inputs | NOT_IMPLEMENTED: AMI build/proof |
| Sandbox default-deny network | Kubernetes NetworkPolicy source exists | BLOCKED on cluster test |
| Sandbox no RDS/Valkey access | network architecture denies direct authorization | BLOCKED on adversarial test |
| Sandbox metadata denial | IMDSv2/hop-limit + no pod credentials architecture | BLOCKED on adversarial test |
| Python production execution | existing local adapter is not production safe | NOT_IMPLEMENTED: async gVisor dispatcher |
| SQL production execution | disposable SQL adapter exists; production job integration pending | NOT_IMPLEMENTED: async gVisor dispatcher |
| Duplicate SQS redelivery safety | required design documented | NOT_IMPLEMENTED |
| Execution cancellation/reconciliation | required design documented | NOT_IMPLEMENTED |
| WAF managed/rate rules | Terraform module exists | BLOCKED on AWS apply verification |
| Queue/RDS/Valkey alarms | Terraform CloudWatch alarms + SNS topic | BLOCKED on AWS apply verification |
| Terraform staging/prod isolation | separate roots/CIDRs/state examples | PASS (source) |
| Production Terraform apply from PR prohibited | PR workflow performs init/validate only | PASS (source) |
| Backup restore validation | not yet automated/executed | NOT_IMPLEMENTED |
| Native store signing/submission | EAS profiles only | NOT_IMPLEMENTED |

Update this matrix as tests produce evidence. Never convert an AWS-related `BLOCKED` entry to `PASS` based only on a successful `terraform validate`.
