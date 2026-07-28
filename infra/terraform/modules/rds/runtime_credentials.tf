resource "random_password" "app" {
  length  = 48
  special = true
  override_special = "!#$%&*+-.:=?@^_~"
}

resource "random_password" "migrator" {
  length  = 48
  special = true
  override_special = "!#$%&*+-.:=?@^_~"
}

resource "aws_secretsmanager_secret" "app" {
  name_prefix             = "${var.name}/postgres/app-"
  kms_key_id              = var.kms_key_arn
  recovery_window_in_days = 30
  tags = merge(local.tags, {
    "rigor:database-role" = "application"
  })
}

resource "aws_secretsmanager_secret_version" "app" {
  secret_id = aws_secretsmanager_secret.app.id
  secret_string = jsonencode({
    username = "rigor_app"
    password = random_password.app.result
    host     = aws_db_instance.this.address
    port     = aws_db_instance.this.port
    dbname   = aws_db_instance.this.db_name
    sslmode  = "require"
  })
}

resource "aws_secretsmanager_secret" "migrator" {
  name_prefix             = "${var.name}/postgres/migrator-"
  kms_key_id              = var.kms_key_arn
  recovery_window_in_days = 30
  tags = merge(local.tags, {
    "rigor:database-role" = "migrator"
  })
}

resource "aws_secretsmanager_secret_version" "migrator" {
  secret_id = aws_secretsmanager_secret.migrator.id
  secret_string = jsonencode({
    username = "rigor_migrator"
    password = random_password.migrator.result
    host     = aws_db_instance.this.address
    port     = aws_db_instance.this.port
    dbname   = aws_db_instance.this.db_name
    sslmode  = "require"
  })
}
