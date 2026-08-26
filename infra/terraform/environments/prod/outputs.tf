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

output "upload_bucket" {
  value = module.storage.upload_bucket_name
}

output "ecs_cluster" {
  value = module.application.cluster_name
}
