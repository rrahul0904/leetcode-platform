# Backup and Recovery Plan

RDS uses encrypted automated backups, point-in-time recovery, cross-region copy where required, and quarterly restore tests. S3 enables versioning, lifecycle policy, and replication according to data classification. Terraform state is remote, encrypted, locked, and separately recoverable. Temporal Cloud recovery follows the verified managed-service contract.

Provisional targets are RPO 15 minutes and RTO 4 hours for the application catalog; identity-provider and sandbox dependencies may have different targets. Targets require cost and business approval before production. Git retains authored content, but it is not a backup for submissions, approvals, or user data.

