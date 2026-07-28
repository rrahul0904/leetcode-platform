variable "name" {
  type = string
}

variable "kms_key_arn" {
  type = string
}

variable "tags" {
  type    = map(string)
  default = {}
}

locals {
  repositories = toset([
    "web",
    "api",
    "trusted-worker",
    "python-runtime",
    "sql-controller",
  ])

  tags = merge(var.tags, {
    "rigor:component" = "container-registry"
  })
}

resource "aws_ecr_repository" "this" {
  for_each = local.repositories

  name                 = "${var.name}/${each.key}"
  image_tag_mutability = "IMMUTABLE"

  encryption_configuration {
    encryption_type = "KMS"
    kms_key         = var.kms_key_arn
  }

  image_scanning_configuration {
    scan_on_push = true
  }

  tags = local.tags
}

resource "aws_ecr_lifecycle_policy" "this" {
  for_each = aws_ecr_repository.this

  repository = each.value.name
  policy = jsonencode({
    rules = [
      {
        rulePriority = 1
        description  = "Expire untagged build layers after fourteen days"
        selection = {
          tagStatus   = "untagged"
          countType   = "sinceImagePushed"
          countUnit   = "days"
          countNumber = 14
        }
        action = { type = "expire" }
      }
    ]
  })
}

output "repository_urls" {
  value = { for key, repository in aws_ecr_repository.this : key => repository.repository_url }
}

output "repository_arns" {
  value = { for key, repository in aws_ecr_repository.this : key => repository.arn }
}
