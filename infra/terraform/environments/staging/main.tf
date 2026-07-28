provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = "Rigor"
      Environment = "staging"
      ManagedBy   = "Terraform"
    }
  }
}

module "rigor" {
  source = "../../modules/platform"

  name        = "rigor-staging"
  environment = "staging"
  vpc_cidr    = "10.40.0.0/16"
  az_count    = 2

  enable_nat_gateway_per_az = false
  enable_control_plane_compute = var.enable_control_plane_compute

  web_image    = var.web_image
  api_image    = var.api_image
  worker_image = var.worker_image

  certificate_arn = var.certificate_arn
  api_host        = var.api_host
  allowed_origins = var.allowed_origins
  oidc_issuer     = var.oidc_issuer
  oidc_audience   = var.oidc_audience
  oidc_jwks_url   = var.oidc_jwks_url

  rds_instance_class      = "db.t4g.medium"
  rds_multi_az            = false
  rds_deletion_protection = false

  valkey_node_type      = "cache.t4g.small"
  valkey_cache_clusters = 1

  kubernetes_version    = var.kubernetes_version
  gvisor_node_ami_id    = var.gvisor_node_ami_id
  gvisor_node_user_data = var.gvisor_node_user_data

  execution_node_min_size     = 0
  execution_node_desired_size = 0
  execution_node_max_size     = 10

  tags = {
    "rigor:environment" = "staging"
  }
}

output "foundation" {
  value = {
    vpc_id                        = module.rigor.vpc_id
    execution_queue_url           = module.rigor.execution_queue_url
    artifacts_bucket_name         = module.rigor.artifacts_bucket_name
    execution_artifact_bucket     = module.rigor.execution_artifact_bucket_name
    execution_cluster_name        = module.rigor.execution_cluster_name
    gvisor_node_group_created     = module.rigor.gvisor_node_group_created
    control_plane_compute_enabled = module.rigor.control_plane_compute_enabled
    load_balancer_dns             = module.rigor.control_plane_load_balancer_dns
  }
}
