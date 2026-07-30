output "execution_queue_url" {
  value       = module.execution_queue.queue_url
  description = "Staging execution queue URL."
}

output "execution_dlq_url" {
  value       = module.execution_queue.dlq_url
  description = "Staging execution DLQ URL."
}

output "execution_queue_kms_key_arn" {
  value       = module.execution_queue.kms_key_arn
  description = "KMS key protecting staging execution queue messages."
}

output "execution_staging_enabled" {
  value       = var.enable_execution_staging_infrastructure
  description = "Whether the cost-bearing representative execution staging stack is enabled."
}

output "execution_registry_urls" {
  value       = try(module.execution_registry[0].repository_urls, {})
  description = "Immutable KMS-encrypted ECR repository URLs keyed by execution component."
}

output "execution_vpc_id" {
  value       = try(module.execution_network[0].vpc_id, null)
  description = "Private execution staging VPC ID when enabled."
}

output "execution_control_subnet_ids" {
  value       = try(module.execution_network[0].control_subnet_ids, [])
  description = "Trusted-control subnet IDs when staging infrastructure is enabled."
}

output "execution_untrusted_subnet_ids" {
  value       = try(module.execution_network[0].execution_subnet_ids, [])
  description = "No-Internet-route hostile execution subnet IDs."
}

output "execution_eks_cluster_name" {
  value       = try(module.execution_eks[0].cluster_name, null)
  description = "Representative execution EKS cluster name."
}

output "execution_node_group_enabled" {
  value       = try(module.execution_eks[0].execution_node_group_enabled, false)
  description = "Whether the custom gVisor-ready hostile execution node group is declared."
}

output "execution_database_endpoint" {
  value       = try(module.execution_database[0].endpoint, null)
  description = "Private staging RDS PostgreSQL endpoint."
}

output "execution_database_master_secret_arn" {
  value       = try(module.execution_database[0].master_user_secret_arn, null)
  description = "AWS-managed RDS master credential secret. Not a candidate execution secret."
  sensitive   = true
}

output "execution_controller_role_arn" {
  value       = try(aws_iam_role.execution_controller[0].arn, null)
  description = "Pod Identity IAM role for the trusted execution controller."
}
