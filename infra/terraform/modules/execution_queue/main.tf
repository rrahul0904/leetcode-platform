resource "aws_kms_key" "execution_queue" {
  description             = "KMS key for ${var.name_prefix} execution SQS queues"
  deletion_window_in_days = 30
  enable_key_rotation     = true

  tags = merge(var.tags, {
    Name      = "${var.name_prefix}-execution-queue"
    Component = "execution"
    DataClass = "candidate-execution-metadata"
  })
}

resource "aws_kms_alias" "execution_queue" {
  name          = "alias/${var.name_prefix}-execution-queue"
  target_key_id = aws_kms_key.execution_queue.key_id
}

resource "aws_sqs_queue" "dlq" {
  name                      = "${var.name_prefix}-execution-dlq"
  message_retention_seconds = var.dlq_retention_seconds
  receive_wait_time_seconds = 20

  kms_master_key_id                 = aws_kms_key.execution_queue.arn
  kms_data_key_reuse_period_seconds = 300

  tags = merge(var.tags, {
    Name      = "${var.name_prefix}-execution-dlq"
    Component = "execution"
    QueueRole = "dead-letter"
  })
}

resource "aws_sqs_queue" "execution" {
  name                       = "${var.name_prefix}-execution"
  visibility_timeout_seconds = var.visibility_timeout_seconds
  message_retention_seconds  = var.message_retention_seconds
  receive_wait_time_seconds  = 20

  kms_master_key_id                 = aws_kms_key.execution_queue.arn
  kms_data_key_reuse_period_seconds = 300

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.dlq.arn
    maxReceiveCount     = var.max_receive_count
  })

  tags = merge(var.tags, {
    Name      = "${var.name_prefix}-execution"
    Component = "execution"
    QueueRole = "dispatch"
  })
}

resource "aws_cloudwatch_metric_alarm" "execution_backlog" {
  alarm_name          = "${var.name_prefix}-execution-backlog"
  alarm_description   = "Execution queue backlog exceeds the configured staging threshold."
  comparison_operator = "GreaterThanOrEqualToThreshold"
  evaluation_periods  = 3
  threshold           = var.queue_depth_alarm_threshold
  metric_name         = "ApproximateNumberOfMessagesVisible"
  namespace           = "AWS/SQS"
  period              = 60
  statistic           = "Maximum"
  treat_missing_data  = "notBreaching"
  alarm_actions       = var.alarm_actions

  dimensions = {
    QueueName = aws_sqs_queue.execution.name
  }

  tags = merge(var.tags, {
    Component = "execution"
    Signal    = "queue-backlog"
  })
}

resource "aws_cloudwatch_metric_alarm" "execution_oldest_message" {
  alarm_name          = "${var.name_prefix}-execution-oldest-message"
  alarm_description   = "An execution has waited in SQS longer than the configured latency threshold."
  comparison_operator = "GreaterThanOrEqualToThreshold"
  evaluation_periods  = 2
  threshold           = var.oldest_message_age_alarm_seconds
  metric_name         = "ApproximateAgeOfOldestMessage"
  namespace           = "AWS/SQS"
  period              = 60
  statistic           = "Maximum"
  treat_missing_data  = "notBreaching"
  alarm_actions       = var.alarm_actions

  dimensions = {
    QueueName = aws_sqs_queue.execution.name
  }

  tags = merge(var.tags, {
    Component = "execution"
    Signal    = "queue-latency"
  })
}

resource "aws_cloudwatch_metric_alarm" "execution_dlq" {
  alarm_name          = "${var.name_prefix}-execution-dlq-visible"
  alarm_description   = "At least one execution message requires DLQ operator investigation."
  comparison_operator = "GreaterThanOrEqualToThreshold"
  evaluation_periods  = 1
  threshold           = 1
  metric_name         = "ApproximateNumberOfMessagesVisible"
  namespace           = "AWS/SQS"
  period              = 60
  statistic           = "Maximum"
  treat_missing_data  = "notBreaching"
  alarm_actions       = var.alarm_actions

  dimensions = {
    QueueName = aws_sqs_queue.dlq.name
  }

  tags = merge(var.tags, {
    Component = "execution"
    Signal    = "dead-letter"
  })
}

data "aws_iam_policy_document" "publisher" {
  statement {
    sid    = "PublishExecutionEvents"
    effect = "Allow"
    actions = [
      "sqs:GetQueueAttributes",
      "sqs:GetQueueUrl",
      "sqs:SendMessage",
    ]
    resources = [aws_sqs_queue.execution.arn]
  }

  statement {
    sid    = "UseExecutionQueueKeyForPublish"
    effect = "Allow"
    actions = [
      "kms:Decrypt",
      "kms:GenerateDataKey*",
    ]
    resources = [aws_kms_key.execution_queue.arn]
  }
}

data "aws_iam_policy_document" "consumer" {
  statement {
    sid    = "ConsumeExecutionEvents"
    effect = "Allow"
    actions = [
      "sqs:ChangeMessageVisibility",
      "sqs:DeleteMessage",
      "sqs:GetQueueAttributes",
      "sqs:GetQueueUrl",
      "sqs:ReceiveMessage",
    ]
    resources = [aws_sqs_queue.execution.arn]
  }

  statement {
    sid       = "DecryptExecutionQueueMessages"
    effect    = "Allow"
    actions   = ["kms:Decrypt"]
    resources = [aws_kms_key.execution_queue.arn]
  }
}

data "aws_iam_policy_document" "dlq_operator" {
  statement {
    sid    = "InspectAndReplayExecutionDlq"
    effect = "Allow"
    actions = [
      "sqs:DeleteMessage",
      "sqs:GetQueueAttributes",
      "sqs:GetQueueUrl",
      "sqs:ReceiveMessage",
      "sqs:StartMessageMoveTask",
      "sqs:CancelMessageMoveTask",
      "sqs:ListMessageMoveTasks",
    ]
    resources = [
      aws_sqs_queue.dlq.arn,
      aws_sqs_queue.execution.arn,
    ]
  }

  statement {
    sid       = "DecryptExecutionDlqMessages"
    effect    = "Allow"
    actions   = ["kms:Decrypt"]
    resources = [aws_kms_key.execution_queue.arn]
  }
}
