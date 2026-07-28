output "endpoint" {
  value = aws_db_instance.this.address
}

output "port" {
  value = aws_db_instance.this.port
}

output "database_name" {
  value = aws_db_instance.this.db_name
}

output "security_group_id" {
  value = aws_security_group.postgres.id
}

output "master_user_secret_arn" {
  description = "Bootstrap/recovery credential only; normal application tasks must not receive it."
  value       = try(aws_db_instance.this.master_user_secret[0].secret_arn, null)
  sensitive   = true
}

output "app_secret_arn" {
  value     = aws_secretsmanager_secret.app.arn
  sensitive = true
}

output "migrator_secret_arn" {
  value     = aws_secretsmanager_secret.migrator.arn
  sensitive = true
}
