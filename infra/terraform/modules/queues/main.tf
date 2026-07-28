variable "name" {
  type = string
}

variable "kms_key_arn" {
  type = string
}

variable "visibility_timeout_seconds" {
  type    = number
  default = 60
}

variable "max_receive_count" {
  type    = number
  default = 4
}

variable "message_retention_seconds" {
  type    = number
  default = 345600
}

variable "tags" {
  type    = map(string)
  default = {}
}

resource "aws_sqs_queue" "execution_dlq" {
  name                      = "${var.name}-execution-dlq"
  message_retention_seconds = 1209600
  kms_master_key_id         = var.kms_key_arn

  tags = merge(var.tags, {
    "rigor:component"   = "execution-queue"
    "rigor:trust-plane" = "execution-control"
  })
}

resource "aws_sqs_queue" "execution" {
  name                       = "${var.name}-execution"
  visibility_timeout_seconds = var.visibility_timeout_seconds
  message_retention_seconds  = var.message_retention_seconds
  receive_wait_time_seconds  = 20
  kms_master_key_id          = var.kms_key_arn

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.execution_dlq.arn
    maxReceiveCount     = var.max_receive_count
  })

  tags = merge(var.tags, {
    "rigor:component"   = "execution-queue"
    "rigor:trust-plane" = "execution-control"
  })
}

resource "aws_sqs_queue_redrive_allow_policy" "execution" {
  queue_url = aws_sqs_queue.execution_dlq.id
  redrive_allow_policy = jsonencode({
    redrivePermission = "byQueue"
    sourceQueueArns   = [aws_sqs_queue.execution.arn]
  })
}

output "execution_queue_url" {
  value = aws_sqs_queue.execution.id
}

output "execution_queue_arn" {
  value = aws_sqs_queue.execution.arn
}

output "execution_dlq_url" {
  value = aws_sqs_queue.execution_dlq.id
}

output "execution_dlq_arn" {
  value = aws_sqs_queue.execution_dlq.arn
}
