locals {
  tags = merge(var.tags, {
    "rigor:component"   = "postgresql"
    "rigor:trust-plane" = "data"
  })
}

resource "aws_db_subnet_group" "this" {
  name       = "${var.name}-postgres"
  subnet_ids = var.subnet_ids
  tags       = local.tags
}

resource "aws_security_group" "postgres" {
  name_prefix = "${var.name}-postgres-"
  description = "PostgreSQL reachable only from trusted Rigor control-plane identities."
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

resource "aws_vpc_security_group_ingress_rule" "trusted_postgres" {
  for_each = var.allowed_security_group_ids

  security_group_id            = aws_security_group.postgres.id
  referenced_security_group_id = each.value
  from_port                    = 5432
  to_port                      = 5432
  ip_protocol                  = "tcp"
  description                  = "PostgreSQL from trusted control-plane security group"
}

resource "aws_db_parameter_group" "this" {
  name_prefix = "${var.name}-postgres18-"
  family      = "postgres18"

  parameter {
    name  = "rds.force_ssl"
    value = "1"
  }

  parameter {
    name         = "log_min_duration_statement"
    value        = "1000"
    apply_method = "immediate"
  }

  tags = local.tags

  lifecycle {
    create_before_destroy = true
  }
}

data "aws_iam_policy_document" "monitoring_assume" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["monitoring.rds.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "monitoring" {
  name_prefix        = "${var.name}-rds-monitoring-"
  assume_role_policy = data.aws_iam_policy_document.monitoring_assume.json
  tags               = local.tags
}

resource "aws_iam_role_policy_attachment" "monitoring" {
  role       = aws_iam_role.monitoring.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonRDSEnhancedMonitoringRole"
}

resource "aws_db_instance" "this" {
  identifier_prefix = "${var.name}-"

  engine         = "postgres"
  engine_version = var.engine_version
  instance_class = var.instance_class

  db_name  = "rigor"
  username = "rigor_admin"
  port     = 5432

  manage_master_user_password   = true
  master_user_secret_kms_key_id = var.kms_key_arn

  allocated_storage     = var.allocated_storage_gib
  max_allocated_storage = var.max_allocated_storage_gib
  storage_type          = "gp3"
  storage_encrypted     = true
  kms_key_id            = var.kms_key_arn

  db_subnet_group_name   = aws_db_subnet_group.this.name
  vpc_security_group_ids = [aws_security_group.postgres.id]
  publicly_accessible    = false
  multi_az               = var.multi_az

  parameter_group_name = aws_db_parameter_group.this.name

  backup_retention_period = var.backup_retention_days
  backup_window           = "03:00-04:00"
  maintenance_window      = "sun:05:00-sun:06:00"

  auto_minor_version_upgrade = true
  apply_immediately           = false
  copy_tags_to_snapshot       = true

  performance_insights_enabled          = var.performance_insights_enabled
  performance_insights_kms_key_id       = var.performance_insights_enabled ? var.kms_key_arn : null
  performance_insights_retention_period = var.performance_insights_enabled ? 7 : null

  monitoring_interval = 60
  monitoring_role_arn = aws_iam_role.monitoring.arn

  deletion_protection       = var.deletion_protection
  skip_final_snapshot       = var.skip_final_snapshot
  final_snapshot_identifier = var.skip_final_snapshot ? null : "${var.name}-final"

  tags = local.tags
}
