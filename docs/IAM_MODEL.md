# Rigor IAM model

## Principles

- Separate ECS task execution role from application task roles.
- Separate web, API, and trusted execution-dispatcher task roles.
- Sandbox pods receive no application IAM role.
- Execution nodes receive only infrastructure permissions required to join EKS and pull approved ECR images.
- KMS use is resource-scoped.

## Web task

The web task role intentionally has no data-plane AWS permissions in the current module.

## API task

The API role can enqueue an execution ID to the execution SQS queue and access the platform artifact bucket/KMS keys needed by trusted API flows. It cannot consume execution messages or administer EKS.

## Trusted dispatcher

The worker role can receive/delete/extend visibility on the execution queue, access the execution-artifact bucket/KMS key, and describe the one execution cluster. EKS access is additionally granted with an EKS access entry scoped to the `rigor-execution` namespace using edit-level Kubernetes permissions.

The dispatcher role is never injected into candidate pods.

## ECS task execution role

The ECS execution role pulls images/writes task logs and may resolve only explicitly enumerated Secrets Manager records at task startup. Normal application code does not inherit that role.

## Database

RDS-managed master credentials are bootstrap/recovery only. `rigor_app` and `rigor_migrator` are separate generated Secrets Manager credentials. Database grants still need a controlled bootstrap operation before application compute is enabled.

## Execution nodes

Execution nodes use EKS worker/ECR/CNI infrastructure permissions. Their instance metadata requires IMDSv2 and a hop limit of 1. Candidate pods have no ServiceAccount token and must not receive pod identity/IRSA associations.

## Required review before production

Verify AWS IAM Access Analyzer findings, task-definition secret references, EKS access scope, KMS key policies, S3 bucket policies, and that no sandbox namespace ServiceAccount gains AWS permissions.
