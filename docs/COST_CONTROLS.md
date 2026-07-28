# Rigor cost controls

## Execution

Production execution must enforce identity-aware limits before queueing:

- runs per minute;
- submits per minute;
- concurrent executions;
- wall-clock/runtime limits;
- CPU/memory/storage limits;
- account/organization monthly execution allowance.

WAF rate rules are coarse abuse controls and do not replace application quotas.

## Infrastructure controls implemented

- execution nodes default to desired size zero;
- execution node group is not created without validated gVisor inputs;
- staging uses lower-cost data defaults than production;
- S3 execution artifacts expire by default;
- ECR untagged images expire;
- CloudWatch logs have finite retention in the ECS module;
- SQS backlog/age is alarmed.

## Required attribution

Execution and AI usage should be attributable to candidate, organization, feature, runtime/language, model/provider, and artifact/log storage class where appropriate. Do not put candidate IDs directly into uncontrolled CloudWatch metric dimensions; use durable usage records/log analysis for high-cardinality attribution.

## AI

AI quotas are independent from execution quotas. Enforce request and token budgets, entitled models, and organization spend ceilings server-side.

## Review triggers

Do not introduce pre-warmed SQL/sandbox pools until queue latency and startup metrics justify their fixed cost. Likewise, scale execution from queue depth/age/concurrency rather than API CPU.
