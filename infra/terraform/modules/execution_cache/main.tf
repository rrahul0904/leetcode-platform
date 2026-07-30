resource "aws_kms_key" "cache" {
  description             = "${var.name_prefix} Valkey and connection-secret encryption"
  deletion_window_in_days = 7
  enable_key_rotation     = true

  tags = merge(var.tags, {
    Name  = "${var.name_prefix}-valkey"
    Plane = "data"
  })
}

resource "aws_kms_alias" "cache" {
  name          = "alias/${var.name_prefix}-valkey"
  target_key_id = aws_kms_key.cache.key_id
}

resource "aws_elasticache_subnet_group" "this" {
  name       = "${var.name_prefix}-valkey"
  subnet_ids = var.data_subnet_ids

  tags = merge(var.tags, {
    Name  = "${var.name_prefix}-valkey"
    Plane = "data"
  })
}

resource "aws_security_group" "cache" {
  name_prefix = "${var.name_prefix}-valkey-"
  description = "TLS Valkey ingress only from explicitly trusted staging clients."
  vpc_id      = var.vpc_id

  tags = merge(var.tags, {
    Name  = "${var.name_prefix}-valkey"
    Plane = "data"
  })
}

resource "aws_security_group_rule" "trusted_valkey" {
  for_each = var.trusted_client_security_group_ids

  type                     = "ingress"
  description              = "Valkey TLS from trusted staging client"
  security_group_id        = aws_security_group.cache.id
  source_security_group_id = each.value
  protocol                 = "tcp"
  from_port                = 6379
  to_port                  = 6379
}

resource "aws_elasticache_replication_group" "this" {
  replication_group_id = "${var.name_prefix}-valkey"
  description          = "Trusted Rigor staging Valkey cache"

  engine         = "valkey"
  engine_version = var.engine_version
  node_type      = var.node_type
  port           = 6379

  num_cache_clusters         = 2
  automatic_failover_enabled = true
  multi_az_enabled           = true

  subnet_group_name  = aws_elasticache_subnet_group.this.name
  security_group_ids = [aws_security_group.cache.id]

  at_rest_encryption_enabled = true
  kms_key_id                 = aws_kms_key.cache.arn
  transit_encryption_enabled = true
  transit_encryption_mode    = "required"
  auth_token                 = var.auth_token

  snapshot_retention_limit = 1
  snapshot_window          = "04:00-05:00"
  maintenance_window       = "sun:05:00-sun:06:00"
  apply_immediately        = true

  tags = merge(var.tags, {
    Plane = "data"
  })
}

resource "aws_secretsmanager_secret" "connection_url" {
  name                    = "${var.name_prefix}/cache/valkey-url"
  description             = "TLS Valkey connection URL for trusted Rigor staging services"
  kms_key_id              = aws_kms_key.cache.arn
  recovery_window_in_days = 7

  tags = merge(var.tags, {
    Component = "valkey-connection"
    Plane     = "trusted-control"
  })
}

resource "aws_secretsmanager_secret_version" "connection_url" {
  secret_id = aws_secretsmanager_secret.connection_url.id
  secret_string = format(
    "rediss://:%s@%s:%d/0",
    urlencode(var.auth_token),
    aws_elasticache_replication_group.this.primary_endpoint_address,
    aws_elasticache_replication_group.this.port,
  )
}
