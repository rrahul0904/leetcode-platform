data "aws_availability_zones" "available" {
  state = "available"
}

data "aws_region" "current" {}

resource "aws_vpc" "this" {
  cidr_block           = var.vpc_cidr
  enable_dns_support   = true
  enable_dns_hostnames = true

  tags = merge(var.tags, {
    Name  = "${var.name_prefix}-execution"
    Plane = "execution"
  })
}

resource "aws_subnet" "control" {
  count = length(var.control_subnet_cidrs)

  vpc_id                  = aws_vpc.this.id
  cidr_block              = var.control_subnet_cidrs[count.index]
  availability_zone       = data.aws_availability_zones.available.names[count.index]
  map_public_ip_on_launch = false

  tags = merge(var.tags, {
    Name                              = "${var.name_prefix}-control-${count.index + 1}"
    Plane                             = "trusted-control"
    "kubernetes.io/role/internal-elb" = "1"
  })
}

resource "aws_subnet" "execution" {
  count = length(var.execution_subnet_cidrs)

  vpc_id                  = aws_vpc.this.id
  cidr_block              = var.execution_subnet_cidrs[count.index]
  availability_zone       = data.aws_availability_zones.available.names[count.index]
  map_public_ip_on_launch = false

  tags = merge(var.tags, {
    Name  = "${var.name_prefix}-execution-${count.index + 1}"
    Plane = "untrusted-execution"
  })
}

resource "aws_subnet" "data" {
  count = length(var.data_subnet_cidrs)

  vpc_id                  = aws_vpc.this.id
  cidr_block              = var.data_subnet_cidrs[count.index]
  availability_zone       = data.aws_availability_zones.available.names[count.index]
  map_public_ip_on_launch = false

  tags = merge(var.tags, {
    Name  = "${var.name_prefix}-data-${count.index + 1}"
    Plane = "data"
  })
}

# There is deliberately no Internet Gateway and no NAT Gateway in this module.
# Every subnet receives only the implicit VPC-local route plus explicit private
# AWS service endpoints below. In particular, hostile execution nodes cannot
# acquire a 0.0.0.0/0 Internet route through this stack.
resource "aws_route_table" "control" {
  vpc_id = aws_vpc.this.id

  tags = merge(var.tags, {
    Name  = "${var.name_prefix}-control"
    Plane = "trusted-control"
  })
}

resource "aws_route_table" "execution" {
  vpc_id = aws_vpc.this.id

  tags = merge(var.tags, {
    Name  = "${var.name_prefix}-execution"
    Plane = "untrusted-execution"
  })
}

resource "aws_route_table" "data" {
  vpc_id = aws_vpc.this.id

  tags = merge(var.tags, {
    Name  = "${var.name_prefix}-data"
    Plane = "data"
  })
}

resource "aws_route_table_association" "control" {
  count = length(aws_subnet.control)

  subnet_id      = aws_subnet.control[count.index].id
  route_table_id = aws_route_table.control.id
}

resource "aws_route_table_association" "execution" {
  count = length(aws_subnet.execution)

  subnet_id      = aws_subnet.execution[count.index].id
  route_table_id = aws_route_table.execution.id
}

resource "aws_route_table_association" "data" {
  count = length(aws_subnet.data)

  subnet_id      = aws_subnet.data[count.index].id
  route_table_id = aws_route_table.data.id
}

resource "aws_security_group" "endpoints" {
  name_prefix = "${var.name_prefix}-vpce-"
  description = "TLS access to private AWS service endpoints from staging VPC nodes."
  vpc_id      = aws_vpc.this.id

  ingress {
    description = "HTTPS from VPC"
    protocol    = "tcp"
    from_port   = 443
    to_port     = 443
    cidr_blocks = [var.vpc_cidr]
  }

  egress {
    description = "Endpoint responses inside VPC"
    protocol    = "-1"
    from_port   = 0
    to_port     = 0
    cidr_blocks = [var.vpc_cidr]
  }

  tags = merge(var.tags, {
    Name = "${var.name_prefix}-vpce"
  })
}

locals {
  interface_endpoint_services = toset([
    "ec2",
    "ecr.api",
    "ecr.dkr",
    "eks-auth",
    "logs",
    "monitoring",
    "sqs",
    "sts",
    "xray",
  ])
}

resource "aws_vpc_endpoint" "interface" {
  for_each = local.interface_endpoint_services

  vpc_id              = aws_vpc.this.id
  service_name        = "com.amazonaws.${data.aws_region.current.name}.${each.value}"
  vpc_endpoint_type   = "Interface"
  private_dns_enabled = true
  subnet_ids          = aws_subnet.control[*].id
  security_group_ids  = [aws_security_group.endpoints.id]

  tags = merge(var.tags, {
    Name = "${var.name_prefix}-${replace(each.value, ".", "-")}"
  })
}

resource "aws_vpc_endpoint" "s3" {
  vpc_id            = aws_vpc.this.id
  service_name      = "com.amazonaws.${data.aws_region.current.name}.s3"
  vpc_endpoint_type = "Gateway"
  route_table_ids   = [aws_route_table.control.id, aws_route_table.execution.id]

  tags = merge(var.tags, {
    Name = "${var.name_prefix}-s3"
  })
}
