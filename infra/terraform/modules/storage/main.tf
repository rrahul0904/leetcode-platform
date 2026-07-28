variable "name" {
  type = string
}

variable "platform_kms_key_arn" {
  type = string
}

variable "execution_kms_key_arn" {
  type = string
}

variable "execution_retention_days" {
  type    = number
  default = 14
}

variable "tags" {
  type    = map(string)
  default = {}
}

resource "aws_s3_bucket" "artifacts" {
  bucket_prefix = "${var.name}-artifacts-"
  force_destroy = false

  tags = merge(var.tags, {
    "rigor:component"   = "object-storage"
    "rigor:trust-plane" = "control"
  })
}

resource "aws_s3_bucket_public_access_block" "artifacts" {
  bucket = aws_s3_bucket.artifacts.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_versioning" "artifacts" {
  bucket = aws_s3_bucket.artifacts.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "artifacts" {
  bucket = aws_s3_bucket.artifacts.id

  rule {
    apply_server_side_encryption_by_default {
      kms_master_key_id = var.platform_kms_key_arn
      sse_algorithm     = "aws:kms"
    }
    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "artifacts" {
  bucket = aws_s3_bucket.artifacts.id

  rule {
    id     = "abort-incomplete-multipart"
    status = "Enabled"

    filter {}

    abort_incomplete_multipart_upload {
      days_after_initiation = 7
    }
  }
}

resource "aws_s3_bucket" "execution" {
  bucket_prefix = "${var.name}-execution-"
  force_destroy = false

  tags = merge(var.tags, {
    "rigor:component"   = "execution-artifacts"
    "rigor:trust-plane" = "execution-control"
  })
}

resource "aws_s3_bucket_public_access_block" "execution" {
  bucket = aws_s3_bucket.execution.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_versioning" "execution" {
  bucket = aws_s3_bucket.execution.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "execution" {
  bucket = aws_s3_bucket.execution.id

  rule {
    apply_server_side_encryption_by_default {
      kms_master_key_id = var.execution_kms_key_arn
      sse_algorithm     = "aws:kms"
    }
    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "execution" {
  bucket = aws_s3_bucket.execution.id

  rule {
    id     = "expire-transient-execution-artifacts"
    status = "Enabled"

    filter {}

    expiration {
      days = var.execution_retention_days
    }

    noncurrent_version_expiration {
      noncurrent_days = var.execution_retention_days
    }

    abort_incomplete_multipart_upload {
      days_after_initiation = 1
    }
  }
}

output "artifacts_bucket_name" {
  value = aws_s3_bucket.artifacts.id
}

output "artifacts_bucket_arn" {
  value = aws_s3_bucket.artifacts.arn
}

output "execution_bucket_name" {
  value = aws_s3_bucket.execution.id
}

output "execution_bucket_arn" {
  value = aws_s3_bucket.execution.arn
}
