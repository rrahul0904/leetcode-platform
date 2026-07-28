variable "name" {
  type = string
}

variable "tags" {
  type    = map(string)
  default = {}
}

resource "aws_kms_key" "platform" {
  description             = "${var.name} canonical platform data encryption"
  enable_key_rotation     = true
  deletion_window_in_days = 30
  tags = merge(var.tags, {
    Name                = "${var.name}-platform"
    "rigor:trust-plane" = "control"
  })
}

resource "aws_kms_alias" "platform" {
  name          = "alias/${var.name}-platform"
  target_key_id = aws_kms_key.platform.key_id
}

resource "aws_kms_key" "execution" {
  description             = "${var.name} transient execution artifact encryption"
  enable_key_rotation     = true
  deletion_window_in_days = 30
  tags = merge(var.tags, {
    Name                = "${var.name}-execution"
    "rigor:trust-plane" = "execution-control"
  })
}

resource "aws_kms_alias" "execution" {
  name          = "alias/${var.name}-execution"
  target_key_id = aws_kms_key.execution.key_id
}

output "platform_key_arn" {
  value = aws_kms_key.platform.arn
}

output "execution_key_arn" {
  value = aws_kms_key.execution.arn
}
