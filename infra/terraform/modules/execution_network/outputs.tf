output "vpc_id" {
  description = "Execution staging VPC ID."
  value       = aws_vpc.this.id
}

output "vpc_cidr" {
  description = "Execution staging VPC CIDR."
  value       = aws_vpc.this.cidr_block
}

output "control_subnet_ids" {
  description = "Private trusted-control subnet IDs."
  value       = aws_subnet.control[*].id
}

output "execution_subnet_ids" {
  description = "Private untrusted-execution subnet IDs with no Internet default route."
  value       = aws_subnet.execution[*].id
}

output "data_subnet_ids" {
  description = "Private data subnet IDs."
  value       = aws_subnet.data[*].id
}

output "control_route_table_id" {
  description = "Trusted-control route table ID."
  value       = aws_route_table.control.id
}

output "execution_route_table_id" {
  description = "Untrusted-execution route table ID."
  value       = aws_route_table.execution.id
}

output "endpoint_security_group_id" {
  description = "Security group used by private AWS interface endpoints."
  value       = aws_security_group.endpoints.id
}
