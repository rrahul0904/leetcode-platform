output "execution_queue_name" {
  value = aws_sqs_queue.execution.name
}

output "execution_dlq_name" {
  value = aws_sqs_queue.execution_dlq.name
}
