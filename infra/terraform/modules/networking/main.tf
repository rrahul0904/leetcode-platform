data "aws_availability_zones" "available" {
  state = "available"
}

data "aws_region" "current" {}

locals {
  azs  = slice(data.aws_availability_zones.available.names, 0, var.az_count)
  tags = merge(var.tags, { "rigor:component" = "networking" })
}

resource "aws_vpc" "this" {
  cidr_block           = var.vpc_cidr
  enable_dns_support   = true
  enable_dns_hostnames = true

  tags = merge(local.tags, { Name = var.name })
}

resource "aws_internet_gateway" "this" {
  vpc_id = aws_vpc.this.id
  tags   = merge(local.tags, { Name = "${var.name}-igw" })
}

resource "aws_subnet" "public" {
  for_each = { for index, az in local.azs : az => index }

  vpc_id                  = aws_vpc.this.id
  availability_zone       = each.key
  cidr_block              = cidrsubnet(var.vpc_cidr, 4, each.value)
  map_public_ip_on_launch = false

  tags = merge(local.tags, {
    Name                     = "${var.name}-public-${each.key}"
    "rigor:trust-plane"      = "ingress"
    "kubernetes.io/role/elb" = "1"
  })
}

resource "aws_subnet" "application" {
  for_each = { for index, az in local.azs : az => index }

  vpc_id            = aws_vpc.this.id
  availability_zone = each.key
  cidr_block        = cidrsubnet(var.vpc_cidr, 4, each.value + 4)

  tags = merge(local.tags, {
    Name                = "${var.name}-app-${each.key}"
    "rigor:trust-plane" = "control"
  })
}

resource "aws_subnet" "data" {
  for_each = { for index, az in local.azs : az => index }

  vpc_id            = aws_vpc.this.id
  availability_zone = each.key
  cidr_block        = cidrsubnet(var.vpc_cidr, 4, each.value + 8)

  tags = merge(local.tags, {
    Name                = "${var.name}-data-${each.key}"
    "rigor:trust-plane" = "data"
  })
}

resource "aws_subnet" "execution" {
  for_each = { for index, az in local.azs : az => index }

  vpc_id            = aws_vpc.this.id
  availability_zone = each.key
  cidr_block        = cidrsubnet(var.vpc_cidr, 4, each.value + 12)

  tags = merge(local.tags, {
    Name                              = "${var.name}-execution-${each.key}"
    "rigor:trust-plane"               = "hostile-execution"
    "kubernetes.io/role/internal-elb" = "0"
  })
}

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.this.id
  tags   = merge(local.tags, { Name = "${var.name}-public" })
}

resource "aws_route" "public_internet" {
  route_table_id         = aws_route_table.public.id
  destination_cidr_block = "0.0.0.0/0"
  gateway_id             = aws_internet_gateway.this.id
}

resource "aws_route_table_association" "public" {
  for_each = aws_subnet.public

  subnet_id      = each.value.id
  route_table_id = aws_route_table.public.id
}

resource "aws_eip" "nat" {
  for_each = var.enable_nat_gateway_per_az ? aws_subnet.public : {
    (local.azs[0]) = aws_subnet.public[local.azs[0]]
  }

  domain = "vpc"
  tags   = merge(local.tags, { Name = "${var.name}-nat-${each.key}" })

  depends_on = [aws_internet_gateway.this]
}

resource "aws_nat_gateway" "this" {
  for_each = aws_eip.nat

  allocation_id = each.value.id
  subnet_id     = aws_subnet.public[each.key].id
  tags          = merge(local.tags, { Name = "${var.name}-nat-${each.key}" })
}

resource "aws_route_table" "application" {
  for_each = aws_subnet.application

  vpc_id = aws_vpc.this.id
  tags   = merge(local.tags, { Name = "${var.name}-app-${each.key}" })
}

resource "aws_route" "application_internet" {
  for_each = aws_route_table.application

  route_table_id         = each.value.id
  destination_cidr_block = "0.0.0.0/0"
  nat_gateway_id = var.enable_nat_gateway_per_az ? aws_nat_gateway.this[each.key].id : aws_nat_gateway.this[local.azs[0]].id
}

resource "aws_route_table_association" "application" {
  for_each = aws_subnet.application

  subnet_id      = each.value.id
  route_table_id = aws_route_table.application[each.key].id
}

resource "aws_route_table" "data" {
  for_each = aws_subnet.data

  vpc_id = aws_vpc.this.id
  tags   = merge(local.tags, { Name = "${var.name}-data-${each.key}" })
}

resource "aws_route_table_association" "data" {
  for_each = aws_subnet.data

  subnet_id      = each.value.id
  route_table_id = aws_route_table.data[each.key].id
}

resource "aws_route_table" "execution" {
  for_each = aws_subnet.execution

  vpc_id = aws_vpc.this.id
  tags = merge(local.tags, {
    Name                     = "${var.name}-execution-${each.key}"
    "rigor:no-internet-egress" = "true"
  })
}

resource "aws_route_table_association" "execution" {
  for_each = aws_subnet.execution

  subnet_id      = each.value.id
  route_table_id = aws_route_table.execution[each.key].id
}

resource "aws_security_group" "vpc_endpoints" {
  name_prefix = "${var.name}-vpce-"
  description = "TLS entry to trusted VPC endpoints. IAM and sandbox network policy remain authoritative."
  vpc_id      = aws_vpc.this.id

  ingress {
    description = "TLS from this VPC"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = [var.vpc_cidr]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = local.tags
}

locals {
  interface_endpoints = toset([
    "ecr.api",
    "ecr.dkr",
    "logs",
    "sts",
  ])
}

resource "aws_vpc_endpoint" "interface" {
  for_each = local.interface_endpoints

  vpc_id              = aws_vpc.this.id
  service_name        = "com.amazonaws.${data.aws_region.current.name}.${each.value}"
  vpc_endpoint_type   = "Interface"
  private_dns_enabled = true
  subnet_ids          = values(aws_subnet.application)[*].id
  security_group_ids  = [aws_security_group.vpc_endpoints.id]

  tags = merge(local.tags, { Name = "${var.name}-${replace(each.value, ".", "-")}" })
}

resource "aws_vpc_endpoint" "s3" {
  vpc_id            = aws_vpc.this.id
  service_name      = "com.amazonaws.${data.aws_region.current.name}.s3"
  vpc_endpoint_type = "Gateway"
  route_table_ids = concat(
    values(aws_route_table.application)[*].id,
    values(aws_route_table.execution)[*].id,
  )

  tags = merge(local.tags, { Name = "${var.name}-s3" })
}
