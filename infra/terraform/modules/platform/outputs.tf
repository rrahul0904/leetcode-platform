output "vpc_id" {
  value = module.networking.vpc_id
}

output "ecr_repository_urls" {
  value = module.ecr.repository_urls
}

output "execution_queue_url" {
  value = module.queues.execution_queue_url
}

output "execution_dlq_url" {
  value = module.queues.execution_dlq_url
}

output "artifacts_bucket_name" {
  value = module.storage.artifacts_bucket_name
}

output "execution_artifact_bucket_name" {
  value = module.storage.execution_bucket_name
}

output "database_endpoint" {
  value = module.rds.endpoint
}

output "database_app_secret_arn" {
  value     = module.rds.app_secret_arn
  sensitive = true
}

output "database_migrator_secret_arn" {
  value     = module.rds.migrator_secret_arn
  sensitive = true
}

output "valkey_endpoint" {
  value = module.valkey.primary_endpoint_address
}

output "valkey_auth_secret_arn" {
  value     = module.valkey.auth_secret_arn
  sensitive = true
}

output "execution_cluster_name" {
  value = module.execution.cluster_name
}

output "gvisor_node_group_created" {
  value = module.execution.gvisor_node_group_created
}

output "control_plane_compute_enabled" {
  value = local.create_control_compute
}

output "control_plane_load_balancer_dns" {
  value = local.create_control_compute ? module.ecs[0].load_balancer_dns_name : null
}

output "waf_arn" {
  value = local.create_control_compute ? module.waf[0].web_acl_arn : null
}
