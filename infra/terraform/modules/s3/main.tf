variable "name_prefix" {
  type = string
}

variable "force_destroy" {
  type    = bool
  default = false
}

resource "aws_s3_bucket" "uploads" {
  bucket_prefix = "${var.name_prefix}-uploads-"
  force_destroy = var.force_destroy
}

resource "aws_s3_bucket" "exports" {
  bucket_prefix = "${var.name_prefix}-exports-"
  force_destroy = var.force_destroy
}

locals {
  private_buckets = {
    uploads = aws_s3_bucket.uploads.id
    exports = aws_s3_bucket.exports.id
  }
}

resource "aws_s3_bucket_public_access_block" "private" {
  for_each = local.private_buckets

  bucket                  = each.value
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "private" {
  for_each = local.private_buckets
  bucket   = each.value

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_versioning" "private" {
  for_each = local.private_buckets
  bucket   = each.value

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "exports" {
  bucket = aws_s3_bucket.exports.id

  rule {
    id     = "expire-exports"
    status = "Enabled"

    expiration {
      days = 30
    }
  }
}

output "upload_bucket_name" {
  value = aws_s3_bucket.uploads.bucket
}

output "upload_bucket_arn" {
  value = aws_s3_bucket.uploads.arn
}

output "export_bucket_name" {
  value = aws_s3_bucket.exports.bucket
}

output "export_bucket_arn" {
  value = aws_s3_bucket.exports.arn
}
