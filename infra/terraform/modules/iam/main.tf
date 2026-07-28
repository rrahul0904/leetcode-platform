data "aws_partition" "current" {}
data "aws_region" "current" {}
data "aws_caller_identity" "current" {}

locals {
  tags = merge(var.tags, { "rigor:component" = "iam" })
  execution_cluster_arn = var.execution_cluster_name == null ? null : format(
    "arn:%s:eks:%s:%s:cluster/%s",
    data.aws_partition.current.partition,
    data.aws_region.current.name,
    data.aws_caller_identity.current.account_id,
    var.execution_cluster_name,
  )
}

data "aws_iam_policy_document" "ecs_tasks_assume" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "ecs_execution" {
  name_prefix        = "${var.name}-ecs-execution-"
  assume_role_policy = data.aws_iam_policy_document.ecs_tasks_assume.json
  tags               = local.tags
}

resource "aws_iam_role_policy_attachment" "ecs_execution" {
  role       = aws_iam_role.ecs_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

data "aws_iam_policy_document" "ecs_runtime_secrets" {
  dynamic "statement" {
    for_each = length(var.runtime_secret_arns) > 0 ? [1] : []
    content {
      sid       = "ReadRuntimeSecrets"
      effect    = "Allow"
      actions   = ["secretsmanager:GetSecretValue"]
      resources = sort(tolist(var.runtime_secret_arns))
    }
  }

  dynamic "statement" {
    for_each = length(var.runtime_secret_arns) > 0 ? [1] : []
    content {
      sid     = "DecryptRuntimeSecrets"
      effect  = "Allow"
      actions = ["kms:Decrypt"]
      resources = [
        var.platform_kms_key_arn,
        var.execution_kms_key_arn,
      ]
    }
  }
}

resource "aws_iam_role_policy" "ecs_runtime_secrets" {
  count = length(var.runtime_secret_arns) > 0 ? 1 : 0

  name   = "runtime-secrets"
  role   = aws_iam_role.ecs_execution.id
  policy = data.aws_iam_policy_document.ecs_runtime_secrets.json
}

resource "aws_iam_role" "web" {
  name_prefix        = "${var.name}-web-"
  assume_role_policy = data.aws_iam_policy_document.ecs_tasks_assume.json
  tags = merge(local.tags, {
    "rigor:service" = "web"
  })
}

resource "aws_iam_role" "api" {
  name_prefix        = "${var.name}-api-"
  assume_role_policy = data.aws_iam_policy_document.ecs_tasks_assume.json
  tags = merge(local.tags, {
    "rigor:service" = "api"
  })
}

resource "aws_iam_role" "worker" {
  name_prefix        = "${var.name}-trusted-worker-"
  assume_role_policy = data.aws_iam_policy_document.ecs_tasks_assume.json
  tags = merge(local.tags, {
    "rigor:service" = "trusted-worker"
  })
}

data "aws_iam_policy_document" "api" {
  statement {
    sid    = "EnqueueExecutions"
    effect = "Allow"
    actions = [
      "sqs:SendMessage",
      "sqs:GetQueueAttributes",
    ]
    resources = [var.execution_queue_arn]
  }

  statement {
    sid    = "PlatformArtifacts"
    effect = "Allow"
    actions = [
      "s3:GetObject",
      "s3:PutObject",
      "s3:AbortMultipartUpload",
    ]
    resources = ["${var.platform_bucket_arn}/*"]
  }

  statement {
    sid       = "ListPlatformArtifacts"
    effect    = "Allow"
    actions   = ["s3:ListBucket"]
    resources = [var.platform_bucket_arn]
  }

  statement {
    sid     = "PlatformKms"
    effect  = "Allow"
    actions = ["kms:Decrypt", "kms:Encrypt", "kms:GenerateDataKey"]
    resources = [
      var.platform_kms_key_arn,
      var.execution_kms_key_arn,
    ]
  }
}

resource "aws_iam_role_policy" "api" {
  name   = "api-runtime"
  role   = aws_iam_role.api.id
  policy = data.aws_iam_policy_document.api.json
}

data "aws_iam_policy_document" "worker" {
  statement {
    sid    = "ConsumeExecutions"
    effect = "Allow"
    actions = [
      "sqs:ReceiveMessage",
      "sqs:DeleteMessage",
      "sqs:ChangeMessageVisibility",
      "sqs:GetQueueAttributes",
    ]
    resources = [var.execution_queue_arn]
  }

  statement {
    sid    = "ExecutionArtifacts"
    effect = "Allow"
    actions = [
      "s3:GetObject",
      "s3:PutObject",
      "s3:DeleteObject",
      "s3:AbortMultipartUpload",
    ]
    resources = ["${var.execution_bucket_arn}/*"]
  }

  statement {
    sid       = "ListExecutionArtifacts"
    effect    = "Allow"
    actions   = ["s3:ListBucket"]
    resources = [var.execution_bucket_arn]
  }

  statement {
    sid     = "ExecutionKms"
    effect  = "Allow"
    actions = ["kms:Decrypt", "kms:Encrypt", "kms:GenerateDataKey"]
    resources = [var.execution_kms_key_arn]
  }

  dynamic "statement" {
    for_each = local.execution_cluster_arn == null ? [] : [1]
    content {
      sid       = "DescribeExecutionCluster"
      effect    = "Allow"
      actions   = ["eks:DescribeCluster"]
      resources = [local.execution_cluster_arn]
    }
  }
}

resource "aws_iam_role_policy" "worker" {
  name   = "execution-dispatch"
  role   = aws_iam_role.worker.id
  policy = data.aws_iam_policy_document.worker.json
}
