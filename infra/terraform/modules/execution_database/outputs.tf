output "endpoint" {
  description = "Private staging PostgreSQL endpoint."
  value       = aws_db_instance.this.address
}

output "port" {
  description = "Private staging PostgreSQL port."
  value       = aws_db_instance.this.port
}

output "database_name" {
  description = "Initial staging application database name."
  value       = aws_db_instance.this.db_name
}

output "security_group_id" {
  description = "Staging database security group ID."
  value       = aws_security_group.database.id
}

output "master_user_secret_arn" {
  description = "AWS-managed Secrets Manager secret ARN for the RDS master credential."
  value       = aws_db_instance.this.master_user_secret[0].secret_arn
  sensitive   = true
}
