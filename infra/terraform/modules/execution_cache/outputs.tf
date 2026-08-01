output "primary_endpoint_address" {
  description = "Private Valkey primary endpoint."
  value       = aws_elasticache_replication_group.this.primary_endpoint_address
}

output "port" {
  description = "Valkey TLS port."
  value       = aws_elasticache_replication_group.this.port
}

output "security_group_id" {
  description = "Security group protecting the trusted Valkey cache."
  value       = aws_security_group.cache.id
}

output "connection_url_secret_arn" {
  description = "Secrets Manager ARN containing the rediss:// connection URL."
  value       = aws_secretsmanager_secret.connection_url.arn
}

output "kms_key_arn" {
  description = "KMS key protecting Valkey at rest and its connection secret."
  value       = aws_kms_key.cache.arn
}
