variable "background_queue_arn" {
  type = string
}

resource "aws_iam_role_policy" "background_queue" {
  name = "skillforge-background-queue"
  role = aws_iam_role.task.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "sqs:SendMessage",
          "sqs:ReceiveMessage",
          "sqs:DeleteMessage",
          "sqs:ChangeMessageVisibility",
          "sqs:GetQueueAttributes"
        ]
        Resource = [var.background_queue_arn]
      }
    ]
  })
}
