locals {
  common_tags = merge(var.tags, {
    "rigor:environment" = var.environment
    "rigor:managed-by"  = "terraform"
    "rigor:platform"    = "rigor"
  })

  execution_cluster_name = "${var.name}-execution"
  create_control_compute = var.enable_control_plane_compute && var.web_image != null && var.api_image != null
}

module "networking" {
  source = "../networking"

  name                      = var.name
  vpc_cidr                  = var.vpc_cidr
  az_count                  = var.az_count
  enable_nat_gateway_per_az = var.enable_nat_gateway_per_az
  tags                      = local.common_tags
}

module "kms" {
  source = "../kms"

  name = var.name
  tags = local.common_tags
}

module "queues" {
  source = "../queues"

  name        = var.name
  kms_key_arn = module.kms.execution_key_arn
  tags        = local.common_tags
}

module "storage" {
  source = "../storage"

  name                  = var.name
  platform_kms_key_arn  = module.kms.platform_key_arn
  execution_kms_key_arn = module.kms.execution_key_arn
  tags                  = local.common_tags
}

module "rds" {
  source = "../rds"

  name                       = var.name
  vpc_id                     = module.networking.vpc_id
  subnet_ids                 = module.networking.data_subnet_ids
  allowed_security_group_ids = toset([
    module.networking.api_security_group_id,
    module.networking.worker_security_group_id,
  ])
  kms_key_arn          = module.kms.platform_key_arn
  instance_class       = var.rds_instance_class
  multi_az             = var.rds_multi_az
  deletion_protection  = var.rds_deletion_protection
  skip_final_snapshot  = false
  tags                 = local.common_tags
}

module "valkey" {
  source = "../valkey"

  name                       = var.name
  vpc_id                     = module.networking.vpc_id
  subnet_ids                 = module.networking.data_subnet_ids
  allowed_security_group_ids = toset([
    module.networking.api_security_group_id,
    module.networking.worker_security_group_id,
  ])
  kms_key_arn        = module.kms.platform_key_arn
  node_type          = var.valkey_node_type
  num_cache_clusters = var.valkey_cache_clusters
  tags               = local.common_tags
}

module "ecr" {
  source = "../ecr"

  name        = var.name
  kms_key_arn = module.kms.platform_key_arn
  tags        = local.common_tags
}

module "iam" {
  source = "../iam"

  name                      = var.name
  execution_queue_arn       = module.queues.execution_queue_arn
  platform_bucket_arn       = module.storage.artifacts_bucket_arn
  execution_bucket_arn      = module.storage.execution_bucket_arn
  platform_kms_key_arn      = module.kms.platform_key_arn
  execution_kms_key_arn     = module.kms.execution_key_arn
  runtime_secret_arns       = toset([
    module.rds.app_secret_arn,
    module.valkey.auth_secret_arn,
  ])
  execution_cluster_name = local.execution_cluster_name
  tags                   = local.common_tags
}

module "execution" {
  source = "../execution"

  name                       = var.name
  vpc_id                     = module.networking.vpc_id
  vpc_cidr                   = module.networking.vpc_cidr
  subnet_ids                 = module.networking.execution_subnet_ids
  s3_prefix_list_id          = module.networking.s3_prefix_list_id
  kms_key_arn                = module.kms.execution_key_arn
  kubernetes_version         = var.kubernetes_version
  orchestrator_principal_arn = module.iam.worker_task_role_arn
  gvisor_node_ami_id         = var.gvisor_node_ami_id
  gvisor_node_user_data      = var.gvisor_node_user_data
  node_min_size              = var.execution_node_min_size
  node_desired_size          = var.execution_node_desired_size
  node_max_size              = var.execution_node_max_size
  tags                       = local.common_tags
}

module "ecs" {
  count  = local.create_control_compute ? 1 : 0
  source = "../ecs"

  name                   = var.name
  vpc_id                 = module.networking.vpc_id
  public_subnet_ids      = module.networking.public_subnet_ids
  application_subnet_ids = module.networking.application_subnet_ids
  web_security_group_id  = module.networking.web_security_group_id
  api_security_group_id  = module.networking.api_security_group_id
  worker_security_group_id = module.networking.worker_security_group_id

  web_image    = coalesce(var.web_image, "disabled")
  api_image    = coalesce(var.api_image, "disabled")
  worker_image = var.worker_image

  ecs_execution_role_arn = module.iam.ecs_execution_role_arn
  web_task_role_arn      = module.iam.web_task_role_arn
  api_task_role_arn      = module.iam.api_task_role_arn
  worker_task_role_arn   = module.iam.worker_task_role_arn

  certificate_arn = var.certificate_arn
  api_host        = var.api_host

  web_environment = {
    NODE_ENV = "production"
  }

  api_environment = merge(
    {
      RIGOR_ENVIRONMENT               = var.environment
      RIGOR_DATABASE_HOST             = module.rds.endpoint
      RIGOR_DATABASE_PORT             = tostring(module.rds.port)
      RIGOR_DATABASE_NAME             = module.rds.database_name
      RIGOR_DATABASE_SSLMODE          = "require"
      RIGOR_VALKEY_HOST               = module.valkey.primary_endpoint_address
      RIGOR_VALKEY_PORT               = tostring(module.valkey.port)
      RIGOR_VALKEY_TLS                = "true"
      RIGOR_ALLOWED_ORIGINS           = jsonencode(var.allowed_origins)
      RIGOR_LOCAL_OIDC_ENABLED        = "false"
      RIGOR_OIDC_ISSUER               = var.oidc_issuer
      RIGOR_OIDC_AUDIENCE             = var.oidc_audience
      RIGOR_EXECUTION_DISPATCH_MODE   = "SQS"
      RIGOR_EXECUTION_QUEUE_URL       = module.queues.execution_queue_url
      RIGOR_EXECUTION_CLUSTER_NAME    = module.execution.cluster_name
      RIGOR_EXECUTION_ARTIFACT_BUCKET = module.storage.execution_bucket_name
    },
    var.oidc_jwks_url == null ? {} : { RIGOR_OIDC_JWKS_URL = var.oidc_jwks_url },
  )

  api_secrets = {
    RIGOR_DATABASE_USER     = "${module.rds.app_secret_arn}:username::"
    RIGOR_DATABASE_PASSWORD = "${module.rds.app_secret_arn}:password::"
    RIGOR_VALKEY_AUTH_TOKEN = "${module.valkey.auth_secret_arn}:auth_token::"
  }

  worker_environment = {
    RIGOR_ENVIRONMENT               = var.environment
    RIGOR_DATABASE_HOST             = module.rds.endpoint
    RIGOR_DATABASE_PORT             = tostring(module.rds.port)
    RIGOR_DATABASE_NAME             = module.rds.database_name
    RIGOR_DATABASE_SSLMODE          = "require"
    RIGOR_EXECUTION_QUEUE_URL       = module.queues.execution_queue_url
    RIGOR_EXECUTION_CLUSTER_NAME    = module.execution.cluster_name
    RIGOR_EXECUTION_ARTIFACT_BUCKET = module.storage.execution_bucket_name
  }

  worker_secrets = {
    RIGOR_DATABASE_USER     = "${module.rds.app_secret_arn}:username::"
    RIGOR_DATABASE_PASSWORD = "${module.rds.app_secret_arn}:password::"
  }

  tags = local.common_tags
}

module "waf" {
  count  = local.create_control_compute ? 1 : 0
  source = "../waf"

  name         = "${var.name}-control-plane"
  resource_arn = module.ecs[0].load_balancer_arn
  tags         = local.common_tags
}
