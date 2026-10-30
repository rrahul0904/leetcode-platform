module "execution_queue" {
  source = "../../modules/execution_queue"

  name_prefix                = var.name_prefix
  visibility_timeout_seconds = 120
  message_retention_seconds  = 345600
  dlq_retention_seconds      = 1209600
  max_receive_count          = 5

  tags = merge(var.tags, {
    Plane = "execution"
  })
}

# Employer executions use a distinct SQS queue and KMS key. They must never
# enter the learner execution event parser or use the learner DLQ.
module "employer_execution_queue" {
  source = "../../modules/execution_queue"

  name_prefix                = "${var.name_prefix}-employer"
  visibility_timeout_seconds = 120
  message_retention_seconds  = 345600
  dlq_retention_seconds      = 1209600
  max_receive_count          = 5

  tags = merge(var.tags, {
    Plane = "employer-execution"
  })
}
