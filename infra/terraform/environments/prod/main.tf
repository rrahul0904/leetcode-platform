module "network" {
  source = "../../modules/vpc"

  name               = var.name
  availability_zones = var.availability_zones
}

module "registry" {
  source = "../../modules/ecr"

  names = ["skillforge-api", "skillforge-worker"]
}

module "execution_queue" {
  source = "../../modules/sqs"

  name = "${var.name}-execution"
}

module "storage" {
  source = "../../modules/s3"

  name_prefix = var.name
}

module "secrets" {
  source = "../../modules/secrets"

  name_prefix = var.name
  secret_names = [
    "RIGOR_DATABASE_URL",
    "RIGOR_OPERATIONAL_DATABASE_URL",
    "RIGOR_VALKEY_URL",
    "CLERK_WEBHOOK_SECRET",
    "SENTRY_DSN"
  ]
}

module "certificate" {
  source = "../../modules/acm"

  domain_name = var.api_domain
  zone_id     = var.route53_zone_id
}

module "application" {
  source = "../../modules/ecs"

  name               = var.name
  vpc_id             = module.network.vpc_id
  public_subnet_ids  = module.network.public_subnet_ids
  private_subnet_ids = module.network.private_subnet_ids
  api_image           = var.api_image
  worker_image        = var.worker_image
  certificate_arn     = module.certificate.certificate_arn
  execution_queue_arn = module.execution_queue.queue_arn
  upload_bucket_arn   = module.storage.upload_bucket_arn
  export_bucket_arn   = module.storage.export_bucket_arn

  environment = {
    RIGOR_ENVIRONMENT             = "production"
    RIGOR_LOCAL_OIDC_ENABLED      = "false"
    RIGOR_EXECUTION_ADAPTER       = "SQS_FARGATE"
    RIGOR_AI_ADAPTER              = "DETERMINISTIC"
    CLERK_ISSUER                  = var.clerk_issuer
    CLERK_JWKS_URL                = var.clerk_jwks_url
    JWT_AUDIENCE                  = var.jwt_audience
    AWS_REGION                    = var.aws_region
    SQS_EXECUTION_QUEUE_URL       = module.execution_queue.queue_url
    S3_UPLOAD_BUCKET              = module.storage.upload_bucket_name
    S3_EXPORT_BUCKET              = module.storage.export_bucket_name
  }

  secret_arns = module.secrets.secret_arns
}

module "database" {
  source = "../../modules/rds"

  name                       = "${var.name}-postgres"
  vpc_id                     = module.network.vpc_id
  private_subnet_ids         = module.network.private_subnet_ids
  allowed_security_group_ids = [module.application.app_security_group_id]
  deletion_protection        = true
  min_capacity               = 1
  max_capacity               = 16
}

module "cache" {
  source = "../../modules/redis"

  name                       = "${var.name}-valkey"
  vpc_id                     = module.network.vpc_id
  private_subnet_ids         = module.network.private_subnet_ids
  allowed_security_group_ids = [module.application.app_security_group_id]
  auth_token                 = var.valkey_auth_token
}

module "waf" {
  source = "../../modules/waf"

  name    = "${var.name}-waf"
  alb_arn = module.application.alb_arn
}

module "api_dns" {
  source = "../../modules/route53"

  zone_id        = var.route53_zone_id
  record_name    = var.api_domain
  alias_dns_name = module.application.alb_dns_name
  alias_zone_id  = module.application.alb_zone_id
}

module "api_cdn" {
  source = "../../modules/cloudfront"

  name               = "${var.name}-api"
  origin_domain_name = var.api_domain
}
