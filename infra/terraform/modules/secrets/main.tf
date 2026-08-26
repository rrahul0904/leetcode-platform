variable "name_prefix" {
  type = string
}

variable "secret_names" {
  type = set(string)
}

resource "aws_secretsmanager_secret" "this" {
  for_each = var.secret_names

  name                    = "${var.name_prefix}/${each.value}"
  recovery_window_in_days = 7
}

output "secret_arns" {
  value = {
    for key, secret in aws_secretsmanager_secret.this : key => secret.arn
  }
}
