output "vpc_id" {
  value = aws_vpc.this.id
}

output "vpc_cidr" {
  value = aws_vpc.this.cidr_block
}

output "public_subnet_ids" {
  value = values(aws_subnet.public)[*].id
}

output "application_subnet_ids" {
  value = values(aws_subnet.application)[*].id
}

output "data_subnet_ids" {
  value = values(aws_subnet.data)[*].id
}

output "execution_subnet_ids" {
  value = values(aws_subnet.execution)[*].id
}

output "execution_route_table_ids" {
  value = values(aws_route_table.execution)[*].id
}

output "vpc_endpoint_security_group_id" {
  value = aws_security_group.vpc_endpoints.id
}
