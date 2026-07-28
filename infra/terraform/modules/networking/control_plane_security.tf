locals {
  control_services = toset(["web", "api", "trusted-worker"])
}

resource "aws_security_group" "control_service" {
  for_each = local.control_services

  name_prefix = "${var.name}-${each.key}-"
  description = "Rigor ${each.key} ECS tasks; ingress is granted only by service-specific infrastructure."
  vpc_id      = aws_vpc.this.id

  egress {
    description = "Trusted control-plane outbound traffic; application subnets use NAT/endpoints"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(local.tags, {
    Name                = "${var.name}-${each.key}"
    "rigor:trust-plane" = "control"
    "rigor:service"     = each.key
  })
}
