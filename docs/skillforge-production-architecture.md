# SkillForge AI production architecture

## Deployment boundary

SkillForge separates trusted SaaS workloads from untrusted candidate execution.

```text
Candidate browser / mobile
        |
        v
Vercel Next.js + Clerk
        |
        v
CloudFront / WAF / ALB
        |
        v
FastAPI on ECS Fargate
   |        |        |
Aurora    Valkey    private S3
   |
Execution outbox -> SQS -> trusted execution controller -> isolated runner
```

Candidate source code never executes inside Next.js or the FastAPI API process. The durable execution domain already records idempotent requests, submissions, public/hidden test results, and terminal state in PostgreSQL. The existing hardened execution plane remains the preferred security baseline while the Fargate application plane is introduced.

## Identity

Clerk owns passwords, MFA, email verification, social login, sessions, recovery, and OAuth/OIDC. SkillForge stores only the external subject (`users.identity_subject`), provider, verified email metadata, status, roles, and application profile. Clerk user/session events are synchronized through the signed `/api/v1/webhooks/clerk` endpoint with replay protection and webhook idempotency.

## Data

Aurora PostgreSQL is the transactional source of truth. RLS protects candidate-scoped state. Valkey is cache/coordination only. Private S3 stores resumes, profile images, certificates, reports, imports, and exports; PostgreSQL stores only metadata and storage keys.

## Production bootstrap

1. Provision `infra/terraform/environments/prod`.
2. Populate the created Secrets Manager entries; do not commit values.
3. Create least-privilege PostgreSQL application/migrator/executor roles using the existing production database bootstrap process.
4. Run `alembic upgrade head`; the expected head is `20260826_0017`.
5. Configure Clerk issuer/JWKS and the Svix webhook secret.
6. Deploy API/worker images through the ECS deployment workflow.
7. Import and verify the trusted 11,979-question serving bank before declaring content ready.

## Scale path

- ECS API: target-tracking autoscaling; stateless services.
- Aurora Serverless v2: multi-instance writer/reader topology and encrypted backups.
- Valkey: encrypted replication group with failover in production.
- SQS: durable queue plus DLQ.
- S3: private, encrypted, versioned buckets with export lifecycle.
- WAF: AWS managed common rules and API rate limiting.
- CloudFront: TLS-only API distribution; Vercel continues to host the Next.js frontend.
