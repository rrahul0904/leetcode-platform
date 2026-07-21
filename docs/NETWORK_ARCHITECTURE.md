# Network Architecture

CloudFront and WAF terminate the public edge before an ALB routes to ECS web/API services in private subnets. RDS, Valkey, and internal endpoints are data-plane private. Outbound traffic uses explicit egress controls and provider allowlists.

The EKS sandbox plane uses a separate VPC or equally strong routed boundary with no path to application/data subnets. Its default route does not provide internet egress. The execution controller reaches only the narrow sandbox control endpoint; sandboxes cannot call back to the controller.

Development, staging, production, and security/logging use separate AWS accounts where practical. Production has no inbound administrative SSH path.

