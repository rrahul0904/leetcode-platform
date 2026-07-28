# Rigor production network security

## Subnet classes

- public ingress: ALB/NAT only;
- private application: ECS web/API/trusted workers;
- private data: RDS and Valkey;
- isolated execution: EKS hostile-code workers.

## Routing

Trusted application subnets can use NAT and selected VPC endpoints. Data subnets have no default internet route. Execution subnets have no default NAT/internet route.

The execution node security group allows private VPC traffic required for EKS node operation plus HTTPS to the S3 managed prefix list through the S3 gateway endpoint. Candidate pods are still governed by default-deny Kubernetes NetworkPolicy and receive no AWS identity.

## Security groups

Web, API, and trusted worker ECS tasks use different security groups. RDS and Valkey allow only explicitly supplied API/worker security-group identities; they are never publicly addressable and execution nodes are not authorized sources.

The ALB can reach only Next.js port 3001 and FastAPI port 8002 security groups. Next.js/FastAPI accept ingress from the ALB identity rather than broad VPC CIDRs.

## AWS endpoints

Trusted application subnets have private ECR API, ECR Docker, CloudWatch Logs, and STS interface endpoints. S3 uses a gateway endpoint. Endpoint access does not grant API authorization: IAM policies remain required.

## Metadata

Execution instances require IMDSv2 and set metadata hop limit 1. Sandboxes do not receive IAM roles or ServiceAccount tokens. Isolation acceptance tests must still explicitly prove `169.254.169.254` is unreachable from candidate code.

## Future allow lists

No candidate internet access is part of the default architecture. A future network-enabled challenge must use a separate policy/class and narrowly controlled proxy/allow list rather than weakening the default execution namespace.
