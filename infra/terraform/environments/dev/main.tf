module "network" {
  source = "../../modules/vpc"

  name               = "skillforge-dev"
  availability_zones = var.availability_zones
}

module "execution_queue" {
  source = "../../modules/sqs"

  name = "skillforge-dev-execution"
}

module "background_queue" {
  source = "../../modules/sqs"

  name = "skillforge-dev-background"
}

module "storage" {
  source = "../../modules/s3"

  name_prefix   = "skillforge-dev"
  force_destroy = true
}

module "application" {
  source = "../../modules/ecs"

  name                 = "skillforge-dev"
  vpc_id               = module.network.vpc_id
  public_subnet_ids    = module.network.public_subnet_ids
  private_subnet_ids   = module.network.private_subnet_ids
  api_image            = var.api_image
  worker_image         = var.worker_image
  execution_queue_arn  = module.execution_queue.queue_arn
  background_queue_arn = module.background_queue.queue_arn
  upload_bucket_arn    = module.storage.upload_bucket_arn
  export_bucket_arn    = module.storage.export_bucket_arn

  api_desired_count    = 1
  worker_desired_count = 1

  environment = {
    RIGOR_ENVIRONMENT          = "development"
    RIGOR_EXECUTION_ADAPTER    = "KUBERNETES_JOB"
    AWS_REGION                 = var.aws_region
    SQS_EXECUTION_QUEUE_URL    = module.execution_queue.queue_url
    RIGOR_BACKGROUND_QUEUE_URL = module.background_queue.queue_url
    S3_UPLOAD_BUCKET           = module.storage.upload_bucket_name
    S3_EXPORT_BUCKET           = module.storage.export_bucket_name
  }
}

module "database" {
  source = "../../modules/rds"

  name                       = "skillforge-dev-postgres"
  vpc_id                     = module.network.vpc_id
  private_subnet_ids         = module.network.private_subnet_ids
  allowed_security_group_ids = [module.application.app_security_group_id]
  deletion_protection        = false
  min_capacity               = 0.5
  max_capacity               = 2
}

module "cache" {
  source = "../../modules/redis"

  name                       = "skillforge-dev-valkey"
  vpc_id                     = module.network.vpc_id
  private_subnet_ids         = module.network.private_subnet_ids
  allowed_security_group_ids = [module.application.app_security_group_id]
  replicas_per_node_group    = 0
  auth_token                 = var.valkey_auth_token
}
