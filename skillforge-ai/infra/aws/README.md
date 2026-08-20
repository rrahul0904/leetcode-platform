# AWS production deployment starter

1. Build/push `backend/Dockerfile` to ECR.
2. Run FastAPI and workers on private ECS Fargate services behind an ALB/API hostname.
3. Keep execution workers in a separate security boundary from normal SaaS workloads.
4. Store service secrets in AWS Secrets Manager; use task roles instead of static AWS keys.
5. Use S3 for large import/export artifacts and lifecycle policies for generated reports.
6. Use ElastiCache Redis or SQS for production queues depending on workload semantics.
7. Frontend can deploy to Vercel for fastest delivery or Amplify/CloudFront for AWS-native environments.
8. Supabase Cloud remains the MVP DB/Auth/Storage/vector plane. Enterprise mode can move to Aurora PostgreSQL + pgvector/OpenSearch Serverless and Cognito.
9. Enable CloudWatch alarms, structured logs, tracing, Sentry, WAF, TLS, backup/PITR, and budget alerts before production traffic.
10. Terraform modules should own networking, ECS, ALB, ECR, S3, Redis/SQS, secrets, DNS, observability, and environment-specific configuration.
