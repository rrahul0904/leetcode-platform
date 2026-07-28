locals {
  tags = merge(var.tags, {
    "rigor:component"   = "valkey"
    "rigor:trust-plane" = "data"
  })
}

resource "random_password" "auth" {
  length  = 48
  special = false
}

resource "aws_secretsmanager_secret" "auth" {
  name_prefix             = "${var.name}/valkey/auth-"
  kms_key_id              = var.kms_key_arn
  recovery_window_in_days = 30
  tags                    = local.tags
}

resource "aws_secretsmanager_secret_version" "auth" {
  secret_id     = aws_secretsmanager_secret.auth.id
  secret_string = jsonencode({ auth_token = random_password.auth.result })
}

resource "aws_elasticache_subnet_group" "this" {
  name       = "${var.name}-valkey"
  subnet_ids = var.subnet_ids
  tags       = local.tags
}

resource "aws_security_group" "valkey" {
  name_prefix = "${var.name}-valkey-"
  description = "Valkey reachable only from trusted Rigor control-plane identities."
  vpc_id      = var.vpc_id

  egress {
    description = "Stateful response traffic"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = local.tags
}

resource "aws_vpc_security_group_ingress_rule" "trusted_valkey" {
  for_each = var.allowed_security_group_ids

  security_group_id            = aws_security_group.valkey.id
  referenced_security_group_id = each.value
  from_port                    = 6379
  to_port                      = 6379
  ip_protocol                  = "tcp"
  description                  = "Valkey from trusted control-plane security group"
}

resource "aws_elasticache_replication_group" "this" {
  replication_group_id = substr("${var.name}-valkey", 0, 40)
  description          = "Rigor non-canonical cache, quota and coordination store"

  engine         = "valkey"
  node_type      = var.node_type
  port           = 6379
  num_cache_clusters = var.num_cache_clusters

  subnet_group_name  = aws_elasticache_subnet_group.this.name
  security_group_ids = [aws_security_group.valkey.id]

  automatic_failover_enabled = var.num_cache_clusters > 1
  multi_az_enabled           = var.num_cache_clusters > 1

  at_rest_encryption_enabled = true
  kms_key_id                 = var.kms_key_arn
  transit_encryption_enabled = true
  auth_token                 = random_password.auth.result

  snapshot_retention_limit = var.snapshot_retention_limit
  snapshot_window          = "02:00-03:00"
  maintenance_window       = "sun:04:00-sun:05:00"

  auto_minor_version_upgrade = true
  apply_immediately           = false

  tags = local.tags

  depends_on = [aws_secretsmanager_secret_version.auth]
}
