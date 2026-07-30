resource "aws_kms_key" "registry" {
  description             = "${var.name_prefix} execution image registry encryption"
  deletion_window_in_days = 7
  enable_key_rotation     = true

  tags = merge(var.tags, {
    Name  = "${var.name_prefix}-execution-registry"
    Plane = "trusted-control"
  })
}

resource "aws_kms_alias" "registry" {
  name          = "alias/${var.name_prefix}-execution-registry"
  target_key_id = aws_kms_key.registry.key_id
}

locals {
  repositories = toset([
    "execution-controller",
    "python-runner",
    "sql-runner",
    "staging-probe",
  ])
}

resource "aws_ecr_repository" "execution" {
  for_each = local.repositories

  name                 = "${var.name_prefix}/${each.value}"
  image_tag_mutability = "IMMUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  encryption_configuration {
    encryption_type = "KMS"
    kms_key         = aws_kms_key.registry.arn
  }

  tags = merge(var.tags, {
    Name      = "${var.name_prefix}/${each.value}"
    Component = each.value
    Plane     = "execution"
  })
}

resource "aws_ecr_lifecycle_policy" "execution" {
  for_each = aws_ecr_repository.execution

  repository = each.value.name
  policy = jsonencode({
    rules = [
      {
        rulePriority = 1
        description  = "Delete untagged execution images after the staging retention window"
        selection = {
          tagStatus   = "untagged"
          countType   = "sinceImagePushed"
          countUnit   = "days"
          countNumber = var.untagged_image_retention_days
        }
        action = {
          type = "expire"
        }
      }
    ]
  })
}
