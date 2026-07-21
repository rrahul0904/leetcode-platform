# Deployment Blockers and Decisions

## Product-completion blockers

1. Four schema-complete authored questions exist; zero have independent technical/editorial approval or publication. The public-release threshold remains 1,000 reviewed questions, not generated placeholders.
2. Local OIDC, onboarding persistence, permissions, and question RLS exist; production Cognito configuration, MFA, session hardening, and production authorization testing remain.
3. Local candidate execution adapters are not a production sandbox. Production requires a separate EKS/gVisor boundary and security evidence; Docker Compose is not that boundary.
4. The source-backed corpus has 2,534 external references, but broader commercial/forum coverage requires written permission, approved APIs, credentials, retention controls, and ongoing rights review.
5. Human technical and editorial reviewers—and enforced separation of duties—are required before the new hosted packages can be published.

## AWS deployment inputs

- AWS organization/accounts, regions, domain, Route 53 zone, and certificate ownership
- ECR repositories and GitHub OIDC deployment roles
- Cognito domains, user pools, clients, callback/logout URLs, and MFA policy
- RDS PostgreSQL 18 and pgvector compatibility verification in the selected region
- VPC/subnet plan and hard isolation between application, data, and sandbox planes
- S3 retention/classification policy, KMS keys, Secrets Manager hierarchy, and SES identity
- Temporal Cloud namespace/credentials and approved AI providers with consent/retention policy
- Stripe products/prices/webhook endpoints when billing begins
- Observability retention, alert ownership, SLOs, backup targets, and incident response ownership
- Production registry scanning, SBOM, signing identity, vulnerability thresholds, and release approval policy

## Local publication blockers

No external blocker remains for the implemented foundation. A registry push still needs the user to choose Docker Hub, GHCR, or ECR and provide an authenticated destination. Local Docker publication does not need registry credentials.
