module "observability" {
  source = "../observability"

  name                       = var.name
  execution_queue_name       = module.queues.execution_queue_name
  execution_dlq_name         = module.queues.execution_dlq_name
  db_instance_identifier     = module.rds.db_instance_identifier
  valkey_replication_group_id = module.valkey.replication_group_id
  tags                       = local.common_tags
}
