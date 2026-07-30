resource "aws_kms_key" "database" {
  description             = "${var.name_prefix} RDS storage encryption"
  deletion_window_in_days = 7
  enable_key_rotation     = true

  tags = merge(var.tags, {
    Name  = "${var.name_prefix}-database"
    Plane = "data"
  })
}

resource "aws_kms_alias" "database" {
  name          = "alias/${var.name_prefix}-database"
  target_key_id = aws_kms_key.database.key_id
}

resource "aws_db_subnet_group" "this" {
  name       = "${var.name_prefix}-database"
  subnet_ids = var.data_subnet_ids

  tags = merge(var.tags, {
    Name  = "${var.name_prefix}-database"
    Plane = "data"
  })
}

resource "aws_security_group" "database" {
  name_prefix = "${var.name_prefix}-database-"
  description = "PostgreSQL ingress only from explicitly trusted staging clients."
  vpc_id      = var.vpc_id

  tags = merge(var.tags, {
    Name  = "${var.name_prefix}-database"
    Plane = "data"
  })
}

resource "aws_security_group_rule" "trusted_postgresql" {
  for_each = var.trusted_client_security_group_ids

  type                     = "ingress"
  description              = "PostgreSQL from trusted staging client"
  security_group_id        = aws_security_group.database.id
  source_security_group_id = each.value
  protocol                 = "tcp"
  from_port                = 5432
  to_port                  = 5432
}

resource "aws_db_parameter_group" "this" {
  name_prefix = "${var.name_prefix}-pg18-"
  family      = "postgres18"

  parameter {
    name  = "rds.force_ssl"
    value = "1"
  }

  parameter {
    name  = "log_min_duration_statement"
    value = "1000"
  }

  tags = var.tags
}

resource "aws_db_instance" "this" {
  identifier = "${var.name_prefix}-postgres"

  engine         = "postgres"
  engine_version = var.engine_version
  instance_class = var.instance_class

  db_name  = "rigor"
  username = "rigor_admin"
  port     = 5432

  manage_master_user_password   = true
  master_user_secret_kms_key_id = aws_kms_key.database.arn

  allocated_storage     = var.allocated_storage_gib
  max_allocated_storage = var.max_allocated_storage_gib
  storage_type          = "gp3"
  storage_encrypted     = true
  kms_key_id            = aws_kms_key.database.arn

  db_subnet_group_name   = aws_db_subnet_group.this.name
  vpc_security_group_ids = [aws_security_group.database.id]
  publicly_accessible    = false

  parameter_group_name = aws_db_parameter_group.this.name
  multi_az             = var.multi_az

  backup_retention_period = var.backup_retention_days
  backup_window           = "05:00-06:00"
  maintenance_window      = "sun:06:00-sun:07:00"
  auto_minor_version_upgrade = true
  copy_tags_to_snapshot      = true

  enabled_cloudwatch_logs_exports = ["postgresql", "upgrade"]
  performance_insights_enabled    = true

  deletion_protection = false
  skip_final_snapshot = true

  tags = merge(var.tags, {
    Plane = "data"
  })
}
