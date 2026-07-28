output "execution_queue_url" {
  value       = module.execution_queue.queue_url
  description = "Staging execution queue URL."
}

output "execution_dlq_url" {
  value       = module.execution_queue.dlq_url
  description = "Staging execution DLQ URL."
}

output "execution_queue_kms_key_arn" {
  value       = module.execution_queue.kms_key_arn
  description = "KMS key protecting staging execution queue messages."
}
