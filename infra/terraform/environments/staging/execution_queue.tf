module "execution_queue" {
  source = "../../modules/execution_queue"

  name_prefix               = var.name_prefix
  visibility_timeout_seconds = 120
  message_retention_seconds  = 345600
  dlq_retention_seconds      = 1209600
  max_receive_count          = 5

  tags = merge(var.tags, {
    Plane = "execution"
  })
}
