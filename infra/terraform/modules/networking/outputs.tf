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

output "web_security_group_id" {
  value = aws_security_group.control_service["web"].id
}

output "api_security_group_id" {
  value = aws_security_group.control_service["api"].id
}

output "worker_security_group_id" {
  value = aws_security_group.control_service["trusted-worker"].id
}

output "vpc_endpoint_security_group_id" {
  value = aws_security_group.vpc_endpoints.id
}

output "s3_prefix_list_id" {
  description = "AWS-managed S3 prefix list reached through the gateway endpoint; execution node SGs can allow this without general internet egress."
  value       = aws_vpc_endpoint.s3.prefix_list_id
}
