# Feature branch status

Branch: `feature/multiclient-production-foundation`

This branch intentionally combines the first implementation slice from the multi-client and production-infrastructure prompts so their boundaries stay coherent.

## Implemented

- shared Expo candidate application architecture;
- native PKCE + SecureStore;
- candidate home/catalog/practice/progress/profile;
- SQLite local-first code drafts;
- shared transport/query/design packages;
- EAS profiles;
- production network/data/queue/storage/registry/IAM/ECS/EKS/WAF/observability Terraform source;
- gVisor-gated execution node design and restrictive Kubernetes policy manifests;
- isolated staging/production roots;
- PR validation workflow and release/security documentation.

## Still gated

- async SQS/outbox/dispatcher execution;
- production database role bootstrap/migration runner;
- validated gVisor AMI pipeline;
- queue-driven execution capacity autoscaling;
- DNS/CloudFront;
- staging AWS apply/security tests;
- restore drill;
- native store production release.

Application ECS compute remains disabled by default until the async execution milestone is complete.
