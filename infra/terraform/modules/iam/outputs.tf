output "ecs_execution_role_arn" {
  value = aws_iam_role.ecs_execution.arn
}

output "web_task_role_arn" {
  value = aws_iam_role.web.arn
}

output "api_task_role_arn" {
  value = aws_iam_role.api.arn
}

output "worker_task_role_arn" {
  value = aws_iam_role.worker.arn
}
