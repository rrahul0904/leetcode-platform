variable "name_prefix" {
  type = string
}

variable "force_destroy" {
  type    = bool
  default = false
}

resource "aws_kms_key" "storage" {
  description             = "Customer-managed encryption key for private SkillForge objects"
  deletion_window_in_days = 30
  enable_key_rotation     = true
}

resource "aws_kms_alias" "storage" {
  name          = "alias/skillforge-storage"
  target_key_id = aws_kms_key.storage.key_id
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
    bucket_key_enabled = true

    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = aws_kms_key.storage.arn
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


output "kms_key_arn" {
  value = aws_kms_key.storage.arn
}
