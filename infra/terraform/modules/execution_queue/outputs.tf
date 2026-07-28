output "queue_url" {
  description = "Execution request queue URL."
  value       = aws_sqs_queue.execution.url
}

output "queue_arn" {
  description = "Execution request queue ARN."
  value       = aws_sqs_queue.execution.arn
}

output "dlq_url" {
  description = "Execution dead-letter queue URL."
  value       = aws_sqs_queue.dlq.url
}

output "dlq_arn" {
  description = "Execution dead-letter queue ARN."
  value       = aws_sqs_queue.dlq.arn
}

output "kms_key_arn" {
  description = "Customer-managed KMS key protecting execution queue messages."
  value       = aws_kms_key.execution_queue.arn
}

output "publisher_policy_json" {
  description = "Least-privilege IAM policy document for the outbox publisher."
  value       = data.aws_iam_policy_document.publisher.json
}

output "consumer_policy_json" {
  description = "Least-privilege IAM policy document for trusted dispatchers."
  value       = data.aws_iam_policy_document.consumer.json
}

output "dlq_operator_policy_json" {
  description = "IAM policy document for trusted DLQ inspection/replay tooling."
  value       = data.aws_iam_policy_document.dlq_operator.json
}
