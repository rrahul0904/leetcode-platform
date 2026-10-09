output "api_domain" {
  value = var.api_domain
}

output "api_cloudfront_domain" {
  value = module.api_cdn.domain_name
}

output "aurora_endpoint" {
  value     = module.database.endpoint
  sensitive = true
}

output "aurora_master_secret_arn" {
  value     = module.database.master_secret_arn
  sensitive = true
}

output "valkey_endpoint" {
  value     = module.cache.primary_endpoint
  sensitive = true
}

output "execution_queue_url" {
  value = module.execution_queue.queue_url
}

output "execution_queue_dlq_url" {
  value = module.execution_queue.dlq_url
}

output "execution_cluster_name" {
  description = "Production hostile-code EKS cluster when the execution plane is enabled."
  value = var.enable_execution_production_infrastructure ? (
    module.execution_eks[0].cluster_name
  ) : null
}

output "execution_database_endpoint" {
  description = "Isolated execution database endpoint when the execution plane is enabled."
  value = var.enable_execution_production_infrastructure ? (
    module.execution_database[0].endpoint
  ) : null
  sensitive = true
}

output "upload_bucket" {
  value = module.storage.upload_bucket_name
}

output "ecs_cluster" {
  value = module.application.cluster_name
}
