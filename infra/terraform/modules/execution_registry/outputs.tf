output "repository_urls" {
  description = "Execution image repository URLs keyed by component."
  value = {
    for name, repository in aws_ecr_repository.execution : name => repository.repository_url
  }
}

output "repository_arns" {
  description = "Execution image repository ARNs keyed by component."
  value = {
    for name, repository in aws_ecr_repository.execution : name => repository.arn
  }
}

output "kms_key_arn" {
  description = "KMS key protecting execution ECR repositories."
  value       = aws_kms_key.registry.arn
}
